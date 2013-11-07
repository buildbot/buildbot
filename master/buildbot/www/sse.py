# This file is part of .  Buildbot is free software: you can
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
# Copyright  Team Members

from buildbot.util import json
from twisted.web import resource
from twisted.web import server


class EventResource(resource.Resource):
    isLeaf = True

    def __init__(self, master):
        self.master = master

    def render(self, request):
        path = request.postpath
        if path and path[-1] == '':
            path = path[:-1]
        for i, p in enumerate(path):
            if p == '*':
                path[i] = None
        options = request.args
        for k in options:
            if len(options[k]) == 1:
                options[k] = options[k][1]
        try:
            qref = self.master.data.startConsuming(
                (lambda key, msg: self._sendEvent(request, key, msg)),
                options, path)
        except NotImplementedError:
            request.setResponseCode(404)
            request.setHeader('content-type', 'text/plain; charset=utf-8')
            request.write("unimplemented")
            return
        request.setHeader("content-type", "text/event-stream")
        request.write("")
        d = request.notifyFinish()
        d.addBoth(lambda _: qref.stopConsuming())
        return server.NOT_DONE_YET

    def _sendEvent(self, request, event, data):
        # FIXME
        #request.write("event: " + '.'.join(event) + "\n")
        request.write("event: " + 'event' + "\n")
        request.write("data: " + json.dumps(data) + "\n")
        request.write("\n")
