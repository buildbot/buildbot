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

import os, shutil
from twisted.internet import defer, threads
from twisted.python import  util
from twisted.application import strports, service
from twisted.web import server, static
from buildbot import config
from buildbot.util import json
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
            if www.get('public_html') != self.site_public_html:
                need_new_site = True
        else:
            if www['port']:
                need_new_site = True

        if need_new_site:
            self.setup_site(new_config)

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

    def setup_site(self, new_config):

        public_html = self.site_public_html = new_config.www.get('public_html')

        extra_js = new_config.www.get('extra_js', [])
        extra_routes = []
        for js in extra_js:
            js = os.path.join(public_html, "static", "js", os.path.basename(js))
            if not os.path.isdir(js):
                raise ValueError("missing js files in %s: please do buildbot upgrade_master"
                                 " or update_js"%(js,))
            if os.path.exists(os.path.join(js, "routes.js")):
                extra_routes.append(os.path.basename(js)+"/routes")

        new_config.www["extra_routes"] = json.dumps(extra_routes)

        root = static.File(public_html)

        # redirect the root to UI
        root.putChild('', resource.RedirectResource(self.master, 'ui/'))

        # /ui
        root.putChild('ui', ui.UIResource(self.master))

        # /api
        root.putChild('api', rest.RestRootResource(self.master))

        # /ws
        root.putChild('ws', ws.WsResource(self.master))

        self.site = server.Site(root)

