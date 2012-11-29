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
import pkg_resources
from twisted.internet import defer
from twisted.application import strports, service
from twisted.web import server, static
from buildbot import config
from buildbot.www import ui, resource, rest, ws

class WWWService(config.ReconfigurableServiceMixin, service.MultiService):

    def __init__(self, master):
        service.MultiService.__init__(self)
        self.setName('www')
        self.master = master

        self.port = None
        self.port_service = None
        self.site = None
        self.site_public_html = None

    @defer.inlineCallbacks
    def reconfigService(self, new_config):
        www = new_config.www

        need_new_site = False
        if self.site:
            if www.get('public_html') != self.site_public_html or www.get('extra_js',[]) != self.site_extra_js:
                need_new_site = True
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
                self.port_service.setServiceParent(self)

        yield config.ReconfigurableServiceMixin.reconfigService(self,
                                                                new_config)


    def setupSite(self, new_config):
        # use pkg_resources to find buildbot_www; this will eventually allow
        # multiple entry points and join them together via some magic (TODO)
        # TODO: run this at config time and detect the error there
        entry_points = list(pkg_resources.iter_entry_points('buildbot.www'))
        if len(entry_points) < 1:
            raise RuntimeError("could not find buildbot-www; is it installed?")
        elif len(entry_points) > 1:
            raise RuntimeError("only one buildbot.www entry point is supported")
        ep = entry_points[0].load()

        public_html = self.site_public_html = new_config.www.get('public_html')
        root = static.File(public_html)
        static_node = static.File(ep.static_dir)
        root.putChild('static', static_node)
        extra_js = self.site_extra_js = new_config.www.get('extra_js', [])
        extra_routes = []
        for ejs in extra_js:
            ejs = os.path.join(public_html, "static", "js", os.path.basename(ejs))
            if not os.path.isdir(ejs):
                raise ValueError("missing js files in %s: please do buildbot upgrade_master"
                                 " or updatejs"%(ejs,))
            static_node.putChild(os.path.basename(ejs),static.File(ejs))
            if os.path.exists(os.path.join(ejs, "routes.js")):
                extra_routes.append(os.path.basename(ejs)+"/routes")


        # redirect the root to UI
        root.putChild('', resource.RedirectResource(self.master, 'ui/'))

        # /ui
        root.putChild('ui', ui.UIResource(self.master, extra_routes, ep.index_html))

        # /api
        root.putChild('api', rest.RestRootResource(self.master))

        # /ws
        root.putChild('ws', ws.WsResource(self.master))

        self.site = server.Site(root)

