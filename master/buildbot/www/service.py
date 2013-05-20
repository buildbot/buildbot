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

import pkg_resources
from twisted.internet import defer
from twisted.application import strports, service
from twisted.web import server
from buildbot import config
from buildbot.www import rest, ws, sse

class WWWService(config.ReconfigurableServiceMixin, service.MultiService):

    def __init__(self, master):
        service.MultiService.__init__(self)
        self.setName('www')
        self.master = master

        self.port = None
        self.port_service = None
        self.site = None

        # load the apps early, in case something goes wrong in Python land
        epAndApps = [ (ep, ep.load())
                for ep in pkg_resources.iter_entry_points('buildbot.www') ]

        # look for duplicate names
        names = set([ ep.name for ep, app in epAndApps ])
        seen = set()
        dupes = set(n for n in names if n in seen or seen.add(n))
        if dupes:
            raise RuntimeError("duplicate buildbot.www entry points: %s"
                                % (dupes,))

        self.apps = dict((ep.name, app) for (ep, app) in epAndApps)

        if 'base' not in self.apps:
            raise RuntimeError("could not find buildbot-www; is it installed?")

    @defer.inlineCallbacks
    def reconfigService(self, new_config):
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

        if www['port'] != self.port:
            if self.port_service:
                yield defer.maybeDeferred(lambda :
                        self.port_service.disownServiceParent())
                self.port_service = None

            self.port = www['port']
            if self.port:
                port = self.port
                if type(port) is int:
                    port = "tcp:%d" % port
                self.port_service = strports.service(port, self.site)

                # monkey-patch in some code to get the actual Port object
                # returned by endpoint.listen().  But only for tests.
                if port == "tcp:0:interface=127.0.0.1":
                    old_listen = self.port_service.endpoint.listen
                    def listen(factory):
                        d = old_listen(factory)
                        @d.addCallback
                        def keep(port):
                            self._gotPort = port
                            return port
                        return d
                    self.port_service.endpoint.listen = listen

                self.port_service.setServiceParent(self)

        yield config.ReconfigurableServiceMixin.reconfigService(self,
                                                                new_config)

    def getPortnum(self):
        # for tests, when the configured port is 0 and the kernel selects a
        # dynamic port.  This will fail if the monkeypatch in reconfigService
        # was not made.
        return self._gotPort.getHost().port

    def setupSite(self, new_config):
        root = self.apps['base'].resource

        # /api
        root.putChild('api', rest.RestRootResource(self.master))

        # /ws
        root.putChild('ws', ws.WsResource(self.master))

        # /sse
        root.putChild('sse', sse.EventResource(self.master))

        self.site = server.Site(root)
