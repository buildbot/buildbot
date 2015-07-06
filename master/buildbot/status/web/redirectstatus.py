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

from twisted.web import resource, util


class RedirectStatusResource(resource.Resource):

    def __init__(self, status):
        self.status = status

    def get_url(self, request):
        """ Returns the URL of the build if it was built
        """
        revision = request.args.get("revision", [None])[0]

        builder = request.args.get("builder", [None])[0]

        if revision and builder in self.status.getBuilderNames():
            build = self.status.getBuilder(builder).getBuild(0, revision)
            if build:
                number = build.getNumber()
                url = "/builders/%(builder)s/builds/%(number)d" % {
                    'builder': builder,
                    'number': number,
                }
                return url
        return "/waterfall"

    def render(self, request):
        url = self.get_url(request)
        return util.redirectTo(url, request)

    def getChild(self, name, request):
        return self
