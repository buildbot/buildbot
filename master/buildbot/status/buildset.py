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

    def __init__(self, bsid, status, db):
        self.id = bsid
        self.status = status
        self.db = db

    def _get_info(self):
        return self.db.get_buildset_info(self.id)

    # methods for our clients

    def getSourceStamp(self):
        (external_idstring, reason, ssid, complete, results) = self._get_info()
        return self.db.getSourceStampNumberedNow(ssid)

    def getReason(self):
        (external_idstring, reason, ssid, complete, results) = self._get_info()
        return reason
    def getResults(self):
        (external_idstring, reason, ssid, complete, results) = self._get_info()
        return results
    def getID(self):
        # hah, fooled you - this returns the external_idstring!
        (external_idstring, reason, ssid, complete, results) = self._get_info()
        return external_idstring

    def getBuilderNamesAndBuildRequests(self):
        brs = {}
        brids = self.db.get_buildrequestids_for_buildset(self.id)
        for (buildername, brid) in brids.items():
            brs[buildername] = BuildRequestStatus(brid, self.status, self.db)
        return brs

    def getBuilderNames(self):
        brs = self.db.get_buildrequestids_for_buildset(self.id)
        return sorted(brs.keys())

    def getBuildRequests(self):
        brs = self.db.get_buildrequestids_for_buildset(self.id)
        return [BuildRequestStatus(brid, self.status, self.db)
                for brid in brs.values()]

    def isFinished(self):
        (external_idstring, reason, ssid, complete, results) = self._get_info()
        return complete

    def waitUntilFinished(self):
        return self.status._buildset_waitUntilFinished(self.id)

