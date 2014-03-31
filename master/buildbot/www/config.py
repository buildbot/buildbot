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

from buildbot.interfaces import IConfigured
from buildbot.util import json
from buildbot.www import resource
from twisted.internet import defer
from twisted.web.error import Error


class SessionConfigResource(resource.Resource):
    # enable reconfigResource calls
    needsReconfig = True

    def reconfigResource(self, new_config):
        self.config = new_config.www

    def render_GET(self, request):
        return self.asyncRenderHelper(request, self.renderConfig)

    @defer.inlineCallbacks
    def renderConfig(self, request):
        config = {}
        request.setHeader("content-type", 'text/javascript')
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

        def toJson(obj):
            obj = IConfigured(obj).getConfigDict()
            if isinstance(obj, dict):
                return obj
            return repr(obj) + " not yet IConfigured"
        defer.returnValue("this.config = " +
                          json.dumps(config, default=toJson))
