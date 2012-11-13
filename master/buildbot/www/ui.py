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

from twisted.python import util
from buildbot.www import resource

# read the html base page in a html file
_html_f = open(util.sibpath(__file__,"ui.html"))
html = _html_f.read()
_html_f.close()

class UIResource(resource.Resource):
    isLeaf = True

    def __init__(self, master, extra_routes):
        """ Config can pass a static_url for serving
        static stuff directly from apache or nginx
        """
        self.extra_routes = extra_routes
        resource.Resource.__init__(self, master)

    def render(self, request):
        contents = dict(
            base_url = self.base_url,
            static_url = self.static_url,
            ws_url = self.base_url.replace("http:", "ws:"),
            extra_routes = self.extra_routes)
        # IE8 ignore doctype html in corporate intranets
        # this additionnal header removes this behavior and put
        # IE8 in compatibility mode
        request.setHeader("X-UA-Compatible" ,"IE=edge")
        return html % contents
