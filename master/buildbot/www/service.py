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

import os

from buildbot.plugins.db import get_plugins
from buildbot.util import service
from buildbot.www import auth
from buildbot.www import avatar
from buildbot.www import config as wwwconfig
from buildbot.www import rest
from buildbot.www import sse
from twisted.application import strports
from twisted.internet import defer
from twisted.python import log
from twisted.web import server


class WWWService(service.ReconfigurableServiceMixin, service.AsyncMultiService):

    def __init__(self, master):
        service.AsyncMultiService.__init__(self)
        self.setName('www')
        self.master = master

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

        # we're going to need at least the the base plugin (buildbot-www)
        if 'base' not in self.apps:
            raise RuntimeError("could not find buildbot-www; is it installed?")

        root = self.apps.get('base').resource
        for key, plugin in new_config.www.get('plugins', {}).items():
            log.msg("initializing www plugin %r" % (key,))
            if key not in self.apps:
                raise RuntimeError("could not find plugin %s; is it installed?" % (key,))
            self.apps.get(key).setMaster(self.master)
            root.putChild(key, self.apps.get(key).resource)
        known_plugins = set(new_config.www.get('plugins', {})) | set(['base'])
        for plugin_name in set(self.apps.names) - known_plugins:
            log.msg("NOTE: www plugin %r is installed but not "
                    "configured" % (plugin_name,))

        # /
        root.putChild('', wwwconfig.IndexResource(self.master, self.apps.get('base').static_dir))

        # /auth
        root.putChild('auth', auth.AuthRootResource(self.master))

        # /avatar
        root.putChild('avatar', avatar.AvatarResource(self.master))

        # /api
        root.putChild('api', rest.RestRootResource(self.master))

        # /sse
        root.putChild('sse', sse.EventResource(self.master))

        self.root = root

        either = lambda a, b: a if a else b

        rotateLength = either(new_config.www.get('logRotateLength'), self.master.log_rotation.rotateLength)
        maxRotatedFiles = either(new_config.www.get('maxRotatedFiles'), self.master.log_rotation.maxRotatedFiles)

        class RotateLogSite(server.Site):

            """ A Site that logs to a separate file: http.log, and rotate its logs """

            def _openLogFile(self, path):
                try:
                    from twisted.python.logfile import LogFile
                    log.msg("Setting up http.log rotating %s files of %s bytes each" %
                            (maxRotatedFiles, rotateLength))
                    if hasattr(LogFile, "fromFullPath"):  # not present in Twisted-2.5.0
                        return LogFile.fromFullPath(path, rotateLength=rotateLength, maxRotatedFiles=maxRotatedFiles)
                    else:
                        log.msg("WebStatus: rotated http logs are not supported on this version of Twisted")
                except ImportError, e:
                    log.msg("WebStatus: Unable to set up rotating http.log: %s" % e)

                # if all else fails, just call the parent method
                return server.Site._openLogFile(self, path)

        httplog = None
        if new_config.www['logfileName']:
            httplog = os.path.abspath(os.path.join(self.master.basedir, new_config.www['logfileName']))
        self.site = RotateLogSite(root, logPath=httplog)

        # todo: need to store session infos in the db for multimaster
        # rough examination, it looks complicated, as all the session APIs are sync
        self.site.sessionFactory = server.Session

        # convert this to a tuple so it can't be appended anymore (in
        # case some dynamically created resources try to get reconfigs)
        self.reconfigurableResources = tuple(self.reconfigurableResources)

    def resourceNeedsReconfigs(self, resource):
        # flag this resource as needing to know when a reconfig occurs
        self.reconfigurableResources.append(resource)

    def reconfigSite(self, new_config):
        new_config.www['auth'].reconfigAuth(self.master, new_config)
        for rsrc in self.reconfigurableResources:
            rsrc.reconfigResource(new_config)
