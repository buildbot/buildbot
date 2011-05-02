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
from buildbot.status.buildrequest import BuildRequestStatus

class BuildSetStatus:
    implements(interfaces.IBuildSetStatus)

    def __init__(self, bsdict, status):
        self.id = bsdict['bsid']
        self.bsdict = bsdict
        self.status = status
        self.master = status.master

    # methods for our clients

    def getSourceStamp(self):
        return self.master.db.getSourceStampNumberedNow(self.bsdict['sourcestampid'])

    def getReason(self):
        return self.bsdict['reason']

    def getResults(self):
        return self.bsdict['results']

    def getID(self):
        return self.bsdict['external_idstring']

    def isFinished(self):
        return self.bsdict['complete']

    def getBuilderNamesAndBuildRequests(self):
        brs = {}
        brids = self.master.db.get_buildrequestids_for_buildset(self.id)
        for (buildername, brid) in brids.iteritems():
            brs[buildername] = BuildRequestStatus(buildername, brid,
                                                  self.status)
        return brs

    def getBuilderNames(self):
        brs = self.master.db.get_buildrequestids_for_buildset(self.id)
        return sorted(brs.keys())

    def getBuildRequests(self):
        brs = self.master.db.get_buildrequestids_for_buildset(self.id)
        return [BuildRequestStatus(buildername, brid, self.status)
                for buildername, brid in brs.iteritems()]

    def waitUntilFinished(self):
        return self.status._buildset_waitUntilFinished(self.id)

