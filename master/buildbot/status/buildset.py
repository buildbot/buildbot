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

    def getReason(self):
        return self.bsdict['reason']

    def getResults(self):
        return self.bsdict['results']

    def getID(self):
        return self.bsdict['external_idstring']

    def isFinished(self):
        return self.bsdict['complete']

    def getBuilderNamesAndBuildRequests(self):
        # returns a Deferred; undocumented method that may be removed
        # without warning
        d = self.master.db.buildrequests.getBuildRequests(bsid=self.id)
        def get_objects(brdicts):
            return dict([
                (brd['buildername'], BuildRequestStatus(brd['buildername'],
                                            brd['brid'], self.status))
                for brd in brdicts ])
        d.addCallback(get_objects)
        return d

    def getBuilderNames(self):
        d = self.master.db.buildrequests.getBuildRequests(bsid=self.id)
        def get_names(brdicts):
            return sorted([ brd['buildername'] for brd in brdicts ])
        d.addCallback(get_names)
        return d

    def waitUntilFinished(self):
        return self.status._buildset_waitUntilFinished(self.id)

