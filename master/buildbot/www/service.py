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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from future.utils import iteritems

import calendar
import datetime
import os
from binascii import hexlify

import jwt

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

from buildbot.plugins.db import get_plugins
from buildbot.util import bytes2NativeString
from buildbot.util import service
from buildbot.util import unicode2bytes
from buildbot.www import config as wwwconfig
from buildbot.www import auth
from buildbot.www import avatar
from buildbot.www import change_hook
from buildbot.www import rest
from buildbot.www import sse
from buildbot.www import ws

# as per: http://security.stackexchange.com/questions/95972/what-are-requirements-for-hmac-secret-key
# we need 128 bit key for HS256
SESSION_SECRET_LENGTH = 128
SESSION_SECRET_ALGORITHM = "HS256"


class BuildbotSession(server.Session):
    # We deviate a bit from the twisted API in order to implement that.
    # We keep it a subclass of server.Session (to be safe against isinstance),
    # but we re implement all its API.
    # But as there is no support in twisted web for clustered session management, this leaves
    # us with few choice.
    expDelay = datetime.timedelta(weeks=1)

    def __init__(self, site, token=None):
        """
        Initialize a session with a unique ID for that session.
        """
        self.site = site
        assert self.site.session_secret is not None, "site.session_secret is not configured yet!"
        components.Componentized.__init__(self)
        if token:
            self._fromToken(token)
        else:
            self._defaultValue()

    def _defaultValue(self):
        self.user_info = {"anonymous": True}

    def _fromToken(self, token):
        try:
            decoded = jwt.decode(token, self.site.session_secret, algorithms=[SESSION_SECRET_ALGORITHM])
        except jwt.exceptions.ExpiredSignatureError as e:
            raise KeyError(str(e))
        except Exception as e:
            log.err(e, "while decoding JWT session")
            raise KeyError(str(e))
        # might raise KeyError: will be caught by caller, which makes the token invalid
        self.user_info = decoded['user_info']

    def updateSession(self, request):
        """
        Update the cookie after session object was modified
        @param request: the request object which should get a new cookie
        """
        # we actually need to copy some hardcoded constants from twisted :-(

        # Make sure we aren't creating a secure session on a non-secure page
        secure = request.isSecure()

        if not secure:
            cookieString = b"TWISTED_SESSION"
        else:
            cookieString = b"TWISTED_SECURE_SESSION"

        cookiename = b"_".join([cookieString] + request.sitepath)
        request.addCookie(cookiename, self.uid, path=b"/",
                          secure=secure)

    def expire(self):
        # caller must still call self.updateSession() to actually expire it
        self._defaultValue()

    def notifyOnExpire(self, callback):
        raise NotImplementedError("BuildbotSession can't support notify on session expiration")

    def touch(self):
        pass

    @property
    def uid(self):
        """uid is now generated automatically according to the claims.

        This should actually only be used for cookie generation
        """
        exp = datetime.datetime.utcnow() + self.expDelay
        claims = {
            'user_info': self.user_info,
            # Note that we use JWT standard 'exp' field to implement session expiration
            # we completely bypass twisted.web session expiration mechanisms
            'exp': calendar.timegm(datetime.datetime.timetuple(exp))}

        return jwt.encode(claims, self.site.session_secret, algorithm=SESSION_SECRET_ALGORITHM)


class BuildbotSite(server.Site):

    """ A custom Site for Buildbot needs.
        Supports rotating logs, and JWT sessions
    """

    def __init__(self, root, logPath, rotateLength, maxRotatedFiles):
        server.Site.__init__(self, root, logPath=logPath)
        self.rotateLength = rotateLength
        self.maxRotatedFiles = maxRotatedFiles
        self.session_secret = None

    def _openLogFile(self, path):
        self._nativeize = True
        return LogFile.fromFullPath(
            path, rotateLength=self.rotateLength, maxRotatedFiles=self.maxRotatedFiles)

    def setSessionSecret(self, secret):
        self.session_secret = secret

    def makeSession(self):
        """
        Generate a new Session instance, but not store it for future reference
        (because it will be used by another master instance)
        The session will still be cached by twisted.request
        """
        return BuildbotSession(self)

    def getSession(self, uid):
        """
        Get a previously generated session.
        @param uid: Unique ID of the session (a JWT token).
        @type uid: L{bytes}.
        @raise: L{KeyError} if the session is not found.
        """
        return BuildbotSession(self, uid)


class WWWService(service.ReconfigurableServiceMixin, service.AsyncMultiService):
    name = 'www'

    def __init__(self):
        service.AsyncMultiService.__init__(self)

        self.port = None
        self.port_service = None
        self.site = None

        # load the apps early, in case something goes wrong in Python land
        self.apps = get_plugins('www', None, load_now=True)

    @property
    def auth(self):
        return self.master.config.www['auth']

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config):
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
                yield defer.maybeDeferred(lambda:
                                          self.port_service.disownServiceParent())
                self.port_service = None

            self.port = www['port']
            if self.port:
                port = self.port
                if isinstance(port, int):
                    port = "tcp:%d" % port
                self.port_service = strports.service(port, self.site)

                # monkey-patch in some code to get the actual Port object
                # returned by endpoint.listen().  But only for tests.
                if port == "tcp:0:interface=127.0.0.1":
                    if hasattr(self.port_service, 'endpoint'):
                        old_listen = self.port_service.endpoint.listen

                        def listen(factory):
                            d = old_listen(factory)

                            @d.addCallback
                            def keep(port):
                                self._getPort = lambda: port
                                return port
                            return d
                        self.port_service.endpoint.listen = listen
                    else:
                        # older twisted's just have the port sitting there
                        # as an instance attribute
                        self._getPort = lambda: self.port_service._port

                yield self.port_service.setServiceParent(self)

        if not self.port_service:
            log.msg("No web server configured on this master")

        yield service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(self,
                                                                                   new_config)

    def getPortnum(self):
        # for tests, when the configured port is 0 and the kernel selects a
        # dynamic port.  This will fail if the monkeypatch in reconfigService
        # was not made.
        return self._getPort().getHost().port

    def setupSite(self, new_config):
        self.reconfigurableResources = []

        # we're going to need at least the base plugin (buildbot-www)
        if 'base' not in self.apps:
            raise RuntimeError("could not find buildbot-www; is it installed?")

        root = self.apps.get('base').resource
        for key, plugin in iteritems(new_config.www.get('plugins', {})):
            log.msg("initializing www plugin %r" % (key,))
            if key not in self.apps:
                raise RuntimeError(
                    "could not find plugin %s; is it installed?" % (key,))
            app = self.apps.get(key)
            app.setMaster(self.master)
            app.setConfiguration(plugin)
            root.putChild(unicode2bytes(key), app.resource)
        known_plugins = set(new_config.www.get('plugins', {})) | set(['base'])
        for plugin_name in set(self.apps.names) - known_plugins:
            log.msg("NOTE: www plugin %r is installed but not "
                    "configured" % (plugin_name,))

        # /
        root.putChild(b'', wwwconfig.IndexResource(
            self.master, self.apps.get('base').static_dir))

        # /auth
        root.putChild(b'auth', auth.AuthRootResource(self.master))

        # /avatar
        root.putChild(b'avatar', avatar.AvatarResource(self.master))

        # /api
        root.putChild(b'api', rest.RestRootResource(self.master))

        # /ws
        root.putChild(b'ws', ws.WsResource(self.master))

        # /sse
        root.putChild(b'sse', sse.EventResource(self.master))

        # /change_hook
        resource_obj = change_hook.ChangeHookResource(master=self.master)

        # FIXME: this does not work with reconfig
        change_hook_auth = new_config.www.get('change_hook_auth')
        if change_hook_auth is not None:
            resource_obj = self.setupProtectedResource(
                resource_obj, change_hook_auth)
        root.putChild(b"change_hook", resource_obj)

        self.root = root

        rotateLength = new_config.www.get(
            'logRotateLength') or self.master.log_rotation.rotateLength
        maxRotatedFiles = new_config.www.get(
            'maxRotatedFiles') or self.master.log_rotation.maxRotatedFiles

        httplog = None
        if new_config.www['logfileName']:
            httplog = os.path.abspath(
                os.path.join(self.master.basedir, new_config.www['logfileName']))
        self.site = BuildbotSite(root, logPath=httplog, rotateLength=rotateLength,
                                 maxRotatedFiles=maxRotatedFiles)

        self.site.sessionFactory = None

        # Make sure site.master is set. It is required for poller change_hook
        self.site.master = self.master
        # convert this to a tuple so it can't be appended anymore (in
        # case some dynamically created resources try to get reconfigs)
        self.reconfigurableResources = tuple(self.reconfigurableResources)

    def resourceNeedsReconfigs(self, resource):
        # flag this resource as needing to know when a reconfig occurs
        self.reconfigurableResources.append(resource)

    def reconfigSite(self, new_config):
        new_config.www['auth'].reconfigAuth(self.master, new_config)
        cookie_expiration_time = new_config.www.get('cookie_expiration_time')
        if cookie_expiration_time is not None:
            BuildbotSession.expDelay = cookie_expiration_time

        for rsrc in self.reconfigurableResources:
            rsrc.reconfigResource(new_config)

    @defer.inlineCallbacks
    def makeSessionSecret(self):
        state = self.master.db.state
        objectid = yield state.getObjectId(
            "www", "buildbot.www.service.WWWService")

        def create_session_secret():
            # Bootstrap: We need to create a key, that will be shared with other masters
            # and other runs of this master

            # we encode that in hex for db storage convenience
            return bytes2NativeString(hexlify(os.urandom(int(SESSION_SECRET_LENGTH / 8))))

        session_secret = yield state.atomicCreateState(objectid, "session_secret", create_session_secret)
        self.site.setSessionSecret(session_secret)

    def setupProtectedResource(self, resource_obj, checkers):
        @implementer(IRealm)
        class SimpleRealm(object):

            """
            A realm which gives out L{ChangeHookResource} instances for authenticated
            users.
            """

            def requestAvatar(self, avatarId, mind, *interfaces):
                if resource.IResource in interfaces:
                    return (resource.IResource, resource_obj, lambda: None)
                raise NotImplementedError()

        portal = Portal(SimpleRealm(), checkers)
        credentialFactory = guard.BasicCredentialFactory('Protected area')
        wrapper = guard.HTTPAuthSessionWrapper(portal, [credentialFactory])
        return wrapper

    def getUserInfos(self, request):
        session = request.getSession()
        return session.user_info

    def assertUserAllowed(self, request, ep, action, options):
        user_info = self.getUserInfos(request)
        return self.authz.assertUserAllowed(ep, action, options, user_info)
