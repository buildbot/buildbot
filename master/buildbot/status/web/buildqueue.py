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
import json

import time
from twisted.internet import defer
from buildbot.status.web.base import HtmlResource, path_to_buildqueue_json, path_to_json_build_queue
from buildbot import util
from buildbot.status.buildrequest import BuildRequestStatus
from buildbot.status.web.base import path_to_builder, BuildLineMixin, ActionResource, path_to_buildqueue, path_to_root
from buildbot import interfaces
from buildbot.process.buildrequest import BuildRequest, BuildRequestControl

# /buildqueue
from buildbot.status.web.status_json import QueueJsonResource, FilterOut


class BuildQueueResource(HtmlResource):
    pageTitle = "Katana - Build Queue"
    addSlash = True

    def __init__(self):
        HtmlResource.__init__(self)

    @defer.inlineCallbacks
    def content(self, req, cxt):
        status = self.getStatus(req)

        queue = QueueJsonResource(status)
        queue_json = yield queue.asDict(req)
        cxt['instant_json']['queue'] = {"url": status.getBuildbotURL() + path_to_json_build_queue(req),
                                        "data": json.dumps(queue_json, separators=(',', ':')),
                                        "waitForPush": status.master.config.autobahn_push,
                                        "pushFilters": {
                                            "buildStarted": {},
                                            "requestSubmitted": {},
                                            "requestCancelled": {},
                                        }}
        
        template = req.site.buildbot_service.templates.get_template("buildqueue.html")
        defer.returnValue(template.render(**cxt))

    def getChild(self, path, req):
        s = self.getStatus(req)

        if path == "_selected":
            return StatusResourceSelectedBuildQueue(self.getStatus(req))

class StatusResourceSelectedBuildQueue(HtmlResource,BuildLineMixin):

    def __init__(self, status):
        HtmlResource.__init__(self)
        self.status = status

    def getChild(self, path, req):
        if path == "cancelselected":
            return CancelBuildQueueActionResource(self.status)

        return HtmlResource.getChild(self, path, req)

class CancelBuildQueueActionResource(ActionResource):

    def __init__(self, status):
        self.status = status

    @defer.inlineCallbacks
    def performAction(self, req):
        status = self.getStatus(req)
        master = req.site.buildbot_service.master
        c = interfaces.IControl(self.getBuildmaster(req))

        buildrequest = [int(b) for b in req.args.get("cancelselected", []) if b]

        ## get only the buildrequest from the list!
        brdicts = yield master.db.buildrequests.getBuildRequests(claimed=False, brids=buildrequest)

        for brdict in brdicts:
            br = yield BuildRequest.fromBrdict(
                master, brdict)
            b = master.botmaster.builders[brdict['buildername']]
            brc = BuildRequestControl(b, br)
            yield brc.cancel()

        # go back to the buildqueue page
        if req.args.has_key("ajax"):
            defer.returnValue(path_to_buildqueue_json(req))
        else:
            defer.returnValue(path_to_buildqueue(req))
