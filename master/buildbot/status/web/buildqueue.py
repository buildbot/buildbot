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

import time
from twisted.internet import defer
from buildbot.status.web.base import HtmlResource
from buildbot import util
from buildbot.status.buildrequest import BuildRequestStatus
from buildbot.status.web.base import path_to_builder, BuildLineMixin, ActionResource, path_to_buildqueue, path_to_root
from buildbot import interfaces
from buildbot.process.buildrequest import BuildRequest, BuildRequestControl

# /buildqueue
class BuildQueueResource(HtmlResource):
    pageTitle = "Katana - Build Queue"
    addSlash = True

    def __init__(self):
        HtmlResource.__init__(self)

    @defer.inlineCallbacks
    def content(self, req, cxt):
        status = self.getStatus(req)
        master = req.site.buildbot_service.master

        unclaimed_brq = yield master.db.buildrequests.getUnclaimedBuildRequest()

        brstatus = [ { 'brstatus' : BuildRequestStatus(brdict['buildername'], brdict['brid'], status), 'brdict' : brdict}
                for brdict in unclaimed_brq]

        buildqueue = []
        for pb in brstatus:
            bq = {}
            brdict = pb['brdict']
            brs = pb['brstatus']
            builder_status = status.getBuilder(brs.buildername)
            bq['name'] = brs.buildername
            bq['sourcestamps'] = yield brs.getSourceStamps()
            bq['reason'] = brdict['reason']
            submitTime = yield brs.getSubmitTime()
            bq['when'] = time.strftime("%b %d %H:%M:%S",
                      time.localtime(submitTime))
            bq['waiting'] = util.formatInterval(util.now() - submitTime)
            bq['brid'] = brdict['brid']
            builder = status.getBuilder(brs.buildername)
            bq['builder_url'] = path_to_builder(req, builder, False)
            bq['brdict'] = brdict

            #Get compatible slaves
            build_request = yield brs._getBuildRequest()
            if build_request.properties.hasProperty("selected_slave"):
                bq['slaves'] = [build_request.properties.getProperty("selected_slave")]
            else:
                bq['slaves'] = builder_status.slavenames

            buildqueue.append(bq)

        cxt['buildqueue'] =  buildqueue

        
        
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
        defer.returnValue(path_to_buildqueue(req))