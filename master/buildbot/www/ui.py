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

from buildbot.util import json
from twisted.web import static
from twisted.python import util
import buildbot

class UIResource(static.Data):

    def __init__(self, master, apps):
        data = self.buildIndexHtml(master, apps)
        static.Data.__init__(self, data, 'text/html')

    def buildIndexHtml(self, master, apps):
        # calculate the package dict, with location, for each app's packages,
        # and also gather up routes
        packages = []
        routes = []
        for name, app in apps.iteritems():
            for pkg in app.packages:
                if isinstance(pkg, dict):
                    pkg = pkg.copy()
                else:
                    pkg = { 'name' : pkg }
                pkg['location'] = ('app/%s/%s'
                        % (name, pkg.get('location', pkg['name'])))
                packages.append(pkg)
            routes.extend(app.routes)

        # keep some application metadata, too
        appInfo = [ { 'name' : name,
                      'description': app.description,
                      'version' : app.version }
                    for name, app in apps.iteritems() ]

        # remove a trailing slash from the base URL
        baseUrl = master.config.www['url'].rstrip('/')

        dojoConfig = {
            'async' : 1,
            'tlmSiblingOfDojo' : 0,
            'baseUrl' : baseUrl,
            'packages' : packages,
            'bb' : {
                'wsUrl' : baseUrl.replace('http:', 'ws:') + '/ws',
                'appInfo' : appInfo,
                'routes' : routes,
                'buildbotVersion' : buildbot.version,
            },
        }
        subs = {
            'baseUrl': baseUrl,
            'buildbotVersion' : buildbot.version,
            'dojoConfigJson': json.dumps(dojoConfig, indent=4),
        }
        return open(util.sibpath(__file__, 'index.html')).read() % subs

    def render_GET(self, request):
        # IE8 ignores doctype html in corporate intranets.
        # this additionnal header removes this behavior and puts
        # IE8 in "super-standard" mode.
        request.setHeader("X-UA-Compatible" ,"IE=edge")
        return static.Data.render_GET(self, request)
