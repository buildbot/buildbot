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

from zope.interface import implements
from buildbot import interfaces
from buildbot.util.eventual import eventually

class BuildRequestStatus:
    implements(interfaces.IBuildRequestStatus)

    def __init__(self, brid, status, db):
        self.brid = brid
        self.status = status
        self.db = db

    def buildStarted(self, build):
        self.status._buildrequest_buildStarted(build.status)
        self.builds.append(build.status)

    # methods called by our clients
    def getSourceStamp(self):
        br = self.db.getBuildRequestWithNumber(self.brid)
        return br.source
    def getBuilderName(self):
        br = self.db.getBuildRequestWithNumber(self.brid)
        return br.buildername
    def getBuilds(self):
        builder = self.status.getBuilder(self.getBuilderName())
        builds = []
        buildnums = sorted(self.db.get_buildnums_for_brid(self.brid))
        for buildnum in buildnums:
            bs = builder.getBuild(buildnum)
            if bs:
                builds.append(bs)
        return builds

    def subscribe(self, observer):
        oldbuilds = self.getBuilds()
        for bs in oldbuilds:
            eventually(observer, bs)
        self.status._buildrequest_subscribe(self.brid, observer)
    def unsubscribe(self, observer):
        self.status._buildrequest_unsubscribe(self.brid, observer)

    def getSubmitTime(self):
        br = self.db.getBuildRequestWithNumber(self.brid)
        return br.submittedAt

    def asDict(self):
        result = {}
        # Constant
        result['source'] = self.getSourceStamp().asDict()
        result['builderName'] = self.getBuilderName()
        result['submittedAt'] = self.getSubmitTime()

        # Transient
        result['builds'] = [build.asDict() for build in self.getBuilds()]
        return result
