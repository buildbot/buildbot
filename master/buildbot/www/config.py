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

import jinja2

from buildbot.interfaces import IConfigured
from buildbot.util import json
from buildbot.www import resource
from twisted.internet import defer
from twisted.web.error import Error


class IndexResource(resource.Resource):
    # enable reconfigResource calls
    needsReconfig = True

    def __init__(self, master, staticdir):
        resource.Resource.__init__(self, master)
        loader = jinja2.FileSystemLoader(staticdir)
        self.jinja = jinja2.Environment(loader=loader, undefined=jinja2.StrictUndefined)

    def reconfigResource(self, new_config):
        self.config = new_config.www

        versions = self.getEnvironmentVersions()

        if isinstance(self.config.get('versions'), list):
            versions += self.config['versions']

        self.config['versions'] = versions

    def render_GET(self, request):
        return self.asyncRenderHelper(request, self.renderIndex)

    def getEnvironmentVersions(self):
        import sys
        import twisted
        from buildbot import version as bbversion

        pyversion = '.'.join(map(str, sys.version_info[:3]))

        tx_version_info = (twisted.version.major,
                           twisted.version.minor,
                           twisted.version.micro)
        txversion = '.'.join(map(str, tx_version_info))

        return [
            ('Python', pyversion),
            ('Buildbot', bbversion),
            ('Twisted', txversion),
        ]

    @defer.inlineCallbacks
    def renderIndex(self, request):
        config = {}
        request.setHeader("content-type", 'text/html')
        request.setHeader("Cache-Control", "public;max-age=0")

        session = request.getSession()
        try:
            yield self.config['auth'].maybeAutoLogin(request)
        except Error, e:
            config["on_load_warning"] = e.message

        if hasattr(session, "user_info"):
            config.update({"user": session.user_info})
        else:
            config.update({"user": {"anonymous": True}})

        config.update(self.config)
        config['buildbotURL'] = self.master.config.buildbotURL
        config['title'] = self.master.config.title
        config['titleURL'] = self.master.config.titleURL
        config['multiMaster'] = self.master.config.multiMaster
        if "wamp" in self.master.config.protocols:
            config['wamp'] = self.master.config.protocols['wamp']

        def toJson(obj):
            obj = IConfigured(obj).getConfigDict()
            if isinstance(obj, dict):
                return obj
            return repr(obj) + " not yet IConfigured"

        tpl = self.jinja.get_template('index.html')
        tpl = tpl.render(configjson=json.dumps(config, default=toJson),
                         config=self.config)
        defer.returnValue(tpl.encode("ascii"))
