# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from __future__ import annotations

import calendar
import datetime
import os
from binascii import hexlify
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import cast

import jwt
import twisted
from packaging.version import parse as parse_version
from twisted.application import strports
from twisted.cred.portal import IRealm
from twisted.cred.portal import Portal
from twisted.internet import defer
from twisted.python import components
from twisted.python import log
from twisted.python.logfile import LogFile
from twisted.web import guard
from twisted.web import resource
from twisted.web import server
from zope.interface import implementer

from buildbot import config
from buildbot.plugins.db import get_plugins
from buildbot.util import bytes2unicode
from buildbot.util import service
from buildbot.util import unicode2bytes
from buildbot.www import auth
from buildbot.www import avatar
from buildbot.www import change_hook
from buildbot.www import config as wwwconfig
from buildbot.www import resource as buildbot_resource
from buildbot.www import rest
from buildbot.www import sse
from buildbot.www import ws

if TYPE_CHECKING:
    from twisted.application.internet import StreamServerEndpointService

    from buildbot.master import BuildMaster
    from buildbot.util.twisted import InlineCallbacksType


class BuildbotSession(server.Session):
    # We deviate a bit from the twisted API in order to implement that.
    # We keep it a subclass of server.Session (to be safe against isinstance),
    # but we re implement all its API.
    # But as there is no support in twisted web for clustered session management, this leaves
    # us with few choice.
    expDelay = datetime.timedelta(weeks=1)

    def __init__(self, site: BuildbotSite, token: str | None = None) -> None:
        """
        Initialize a session with a unique ID for that session.
        """
        self.site = site
        assert self.site.session_secret is not None, "site.session_secret is not configured yet!"
        # Cannot use super() here as it would call server.Session.__init__
        # which we explicitly want to override. However, we still want to call
        # server.Session parent class constructor
        components.Componentized.__init__(self)
        if token:
            self._set_user_info_from_token(token)
        else:
            self._defaultValue()

    def _defaultValue(self) -> None:
        self.user_info = auth.build_anonymous_user_info()

    def _set_user_info_from_token(self, token: str) -> None:
        self.user_info = auth.parse_user_info_from_token(token, self.site.session_secret)

    def updateSession(self, request: server.Request) -> None:
        """
        Update the cookie after session object was modified
        @param request: the request object which should get a new cookie
        """
        cookiename = auth.build_cookie_name(request.isSecure(), request.sitepath)  # type: ignore[attr-defined]
        request.addCookie(cookiename, self.uid, path=b"/", secure=request.isSecure())

    def expire(self) -> None:
        # caller must still call self.updateSession() to actually expire it
        self._defaultValue()

    def notifyOnExpire(self, callback: Callable) -> None:
        raise NotImplementedError("BuildbotSession can't support notify on session expiration")

    def touch(self) -> None:
        pass

    @property
    def uid(self) -> str:
        """uid is now generated automatically according to the claims.

        This should actually only be used for cookie generation
        """
        exp = datetime.datetime.now(datetime.timezone.utc) + self.expDelay
        claims = {
            'user_info': self.user_info,
            # Note that we use JWT standard 'exp' field to implement session expiration
            # we completely bypass twisted.web session expiration mechanisms
            'exp': calendar.timegm(datetime.datetime.timetuple(exp)),
        }

        return jwt.encode(claims, self.site.session_secret, algorithm=auth.SESSION_SECRET_ALGORITHM)


class BuildbotSite(server.Site):
    """A custom Site for Buildbot needs.
    Supports rotating logs, and JWT sessions
    """

    master: BuildMaster | None = None

    def __init__(
        self, root: resource.Resource, logPath: str | None, rotateLength: int, maxRotatedFiles: int
    ) -> None:
        super().__init__(root, logPath=logPath)
        self.rotateLength = rotateLength
        self.maxRotatedFiles = maxRotatedFiles
        self.session_secret: str | None = None

    def _openLogFile(self, path: str | bytes) -> LogFile:
        self._nativeize = True
        return LogFile.fromFullPath(
            path, rotateLength=self.rotateLength, maxRotatedFiles=self.maxRotatedFiles
        )

    def getResourceFor(self, request: server.Request) -> resource.Resource:
        request.responseHeaders.removeHeader('Server')
        return server.Site.getResourceFor(self, request)

    def setSessionSecret(self, secret: str) -> None:
        self.session_secret = secret

    def makeSession(self) -> BuildbotSession:
        """
        Generate a new Session instance, but not store it for future reference
        (because it will be used by another master instance)
        The session will still be cached by twisted.request
        """
        return BuildbotSession(self)

    def getSession(self, uid: str) -> BuildbotSession:
        """
        Get a previously generated session.
        @param uid: Unique ID of the session (a JWT token).
        @type uid: L{bytes}.
        @raise: L{KeyError} if the session is not found.
        """
        return BuildbotSession(self, uid)


class WWWService(service.ReconfigurableServiceMixin, service.AsyncMultiService):
    _getPort: Callable[[], Any]
    name: str | None = 'www'  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()

        self.port = None
        self.port_service: StreamServerEndpointService | None = None
        self.reconfigurableResources: (
            list[buildbot_resource.Resource] | tuple[buildbot_resource.Resource, ...]
        ) = []
        self.site: BuildbotSite | None = None

        # load the apps early, in case something goes wrong in Python land
        self.apps = get_plugins('www', None, load_now=True)
        self.base_plugin_name = 'base'

    @property
    def auth(self) -> Any:
        return self.master.config.www['auth']

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config: Any) -> InlineCallbacksType[None]:
        www = new_config.www

        self.authz = www.get('authz')
        if self.authz is not None:
            self.authz.setMaster(self.master)
        need_new_site = False
        if self.site:
            # if config params have changed, set need_new_site to True.
            # There are none right now.
            need_new_site = False
        else:
            if www['port']:
                need_new_site = True

        if need_new_site:
            self.setupSite(new_config)

        if self.site:
            self.reconfigSite(new_config)
            yield self.makeSessionSecret()

        if www['port'] != self.port:
            if self.port_service:
                yield self.port_service.disownServiceParent()
                self.port_service = None

            self.port = www['port']
            if self.port:
                port = self.port
                if isinstance(port, int):
                    port = f"tcp:{port}"
                self.port_service = strports.service(port, self.site)

                # monkey-patch in some code to get the actual Port object
                # returned by endpoint.listen().  But only for tests.
                if port == "tcp:0:interface=127.0.0.1":
                    if hasattr(self.port_service, 'endpoint'):
                        old_listen: Any = self.port_service.endpoint.listen

                        @defer.inlineCallbacks
                        def listen(factory: Any) -> InlineCallbacksType[Any]:
                            port = yield old_listen(factory)
                            self._getPort = lambda: port
                            return port

                        self.port_service.endpoint.listen = listen
                    else:
                        # older twisted's just have the port sitting there
                        # as an instance attribute
                        self._getPort = lambda: self.port_service._port  # type: ignore[union-attr]

                yield self.port_service.setServiceParent(self)

        if not self.port_service:
            log.msg("No web server configured on this master")

        yield super().reconfigServiceWithBuildbotConfig(new_config)

    def getPortnum(self) -> int:
        # for tests, when the configured port is 0 and the kernel selects a
        # dynamic port.  This will fail if the monkeypatch in reconfigService
        # was not made.
        return self._getPort().getHost().port

    def refresh_base_plugin_name(self, new_config: Any) -> None:
        if 'base_react' in new_config.www.get('plugins', {}):
            config.error(
                "'base_react' plugin is no longer supported. Use 'base' plugin in master.cfg "
                "BuildmasterConfig['www'] dictionary instead. Remove 'buildbot-www-react' and "
                "install 'buildbot-www' package."
            )
        self.base_plugin_name = 'base'

    def configPlugins(self, root: resource.Resource, new_config: Any) -> None:
        plugin_root = root
        current_version = parse_version(twisted.__version__)
        if current_version < parse_version("22.10.0"):
            from twisted.web.resource import NoResource

            plugin_root = NoResource()
        else:
            from twisted.web.pages import notFound

            plugin_root = cast(resource.Resource, notFound())
        root.putChild(b"plugins", plugin_root)

        known_plugins = set(new_config.www.get('plugins', {})) | set([self.base_plugin_name])
        for key, plugin in list(new_config.www.get('plugins', {}).items()):
            log.msg(f"initializing www plugin {key!r}")
            if key not in self.apps:
                raise RuntimeError(f"could not find plugin {key}; is it installed?")
            app = self.apps.get(key)
            app.setMaster(self.master)
            app.setConfiguration(plugin)
            plugin_root.putChild(unicode2bytes(key), app.resource)

        for plugin_name in set(self.apps.names) - known_plugins:
            log.msg(f"NOTE: www plugin {plugin_name!r} is installed but not configured")

    def setupSite(self, new_config: Any) -> None:
        self.refresh_base_plugin_name(new_config)

        assert isinstance(self.reconfigurableResources, list)
        self.reconfigurableResources.clear()

        # we're going to need at least the base plugin (buildbot-www or buildbot-www-react)
        if self.base_plugin_name not in self.apps:
            raise RuntimeError("could not find buildbot-www; is it installed?")

        root = self.apps.get(self.base_plugin_name).resource
        self.configPlugins(root, new_config)
        # /
        root.putChild(
            b'',
            wwwconfig.IndexResource(self.master, self.apps.get(self.base_plugin_name).static_dir),
        )

        # /auth
        root.putChild(b'auth', auth.AuthRootResource(self.master))

        # /avatar
        root.putChild(b'avatar', avatar.AvatarResource(self.master))

        # /api
        root.putChild(b'api', rest.RestRootResource(self.master))

        # /config
        root.putChild(b'config', wwwconfig.ConfigResource(self.master))

        # /ws
        root.putChild(b'ws', ws.WsResource(self.master))

        # /sse
        root.putChild(b'sse', sse.EventResource(self.master))

        # /change_hook
        resource_obj: resource.IResource = change_hook.ChangeHookResource(master=self.master)

        # FIXME: this does not work with reconfig
        change_hook_auth: list | None = new_config.www.get('change_hook_auth')
        if change_hook_auth is not None:
            resource_obj = self.setupProtectedResource(resource_obj, change_hook_auth)
        root.putChild(b"change_hook", cast(resource.Resource, resource_obj))

        self.root = root

        rotateLength = (
            new_config.www.get('logRotateLength') or self.master.log_rotation.rotateLength
        )
        maxRotatedFiles = (
            new_config.www.get('maxRotatedFiles') or self.master.log_rotation.maxRotatedFiles
        )

        httplog = None
        if new_config.www['logfileName']:
            httplog = os.path.abspath(
                os.path.join(self.master.basedir, new_config.www['logfileName'])
            )
        self.site = BuildbotSite(
            root, logPath=httplog, rotateLength=rotateLength, maxRotatedFiles=maxRotatedFiles
        )

        assert self.site is not None

        self.site.sessionFactory = None  # type: ignore[assignment]

        # Make sure site.master is set. It is required for poller change_hook
        self.site.master = self.master
        # convert this to a tuple so it can't be appended anymore (in
        # case some dynamically created resources try to get reconfigs)
        self.reconfigurableResources = tuple(self.reconfigurableResources)

    def resourceNeedsReconfigs(self, resource: buildbot_resource.Resource) -> None:
        # flag this resource as needing to know when a reconfig occurs
        assert isinstance(self.reconfigurableResources, list), (
            "www Resources can no longer be reconfigured"
        )
        self.reconfigurableResources.append(resource)

    def reconfigSite(self, new_config: Any) -> None:
        self.refresh_base_plugin_name(new_config)

        root = self.apps.get(self.base_plugin_name).resource
        self.configPlugins(root, new_config)
        new_config.www['auth'].reconfigAuth(self.master, new_config)
        cookie_expiration_time = new_config.www.get('cookie_expiration_time')
        if cookie_expiration_time is not None:
            BuildbotSession.expDelay = cookie_expiration_time

        for rsrc in self.reconfigurableResources:
            rsrc.reconfigResource(new_config)

    @defer.inlineCallbacks
    def makeSessionSecret(self) -> InlineCallbacksType[None]:
        state = self.master.db.state
        objectid = yield state.getObjectId("www", "buildbot.www.service.WWWService")

        def create_session_secret() -> str:
            # Bootstrap: We need to create a key, that will be shared with other masters
            # and other runs of this master

            # we encode that in hex for db storage convenience
            return bytes2unicode(hexlify(os.urandom(int(auth.SESSION_SECRET_LENGTH / 8))))

        session_secret = yield state.atomicCreateState(
            objectid, "session_secret", create_session_secret
        )

        assert self.site is not None
        self.site.setSessionSecret(session_secret)

    def setupProtectedResource(
        self, resource_obj: resource.IResource, checkers: list
    ) -> resource.IResource:
        @implementer(IRealm)
        class SimpleRealm:
            """
            A realm which gives out L{ChangeHookResource} instances for authenticated
            users.
            """

            def requestAvatar(
                self, avatarId: Any, mind: Any, *interfaces: Any
            ) -> tuple[Any, Any, Callable[[], None]]:
                if resource.IResource in interfaces:
                    return (resource.IResource, resource_obj, lambda: None)
                raise NotImplementedError()

        portal = Portal(SimpleRealm(), checkers)
        credentialFactory = guard.BasicCredentialFactory('Protected area')
        wrapper = guard.HTTPAuthSessionWrapper(portal, [credentialFactory])
        return wrapper

    def getUserInfos(self, request: server.Request) -> dict[str, Any]:
        session = request.getSession()
        return session.user_info

    def assertUserAllowed(
        self, request: server.Request, ep: str, action: str, options: dict[str, Any]
    ) -> bool:
        user_info = self.getUserInfos(request)
        return self.authz.assertUserAllowed(ep, action, options, user_info)
