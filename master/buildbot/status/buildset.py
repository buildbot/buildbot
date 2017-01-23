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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from zope.interface import implementer

from buildbot import interfaces
from buildbot.data import resultspec
from buildbot.status.buildrequest import BuildRequestStatus


@implementer(interfaces.IBuildSetStatus)
class BuildSetStatus:

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
        d = self.master.data.get(('buildrequests', ),
                                 filters=[resultspec.Filter('buildsetid', 'eq', [self.id])])

        @d.addCallback
        def get_objects(brdicts):
            return dict([
                (brd['buildername'], BuildRequestStatus(brd['buildername'],
                                                        brd['brid'], self.status))
                for brd in brdicts])
        return d

    def getBuilderNames(self):
        d = self.master.data.get(('buildrequests', ),
                                 filters=[resultspec.Filter('buildsetid', 'eq', [self.id])])

        @d.addCallback
        def get_names(brdicts):
            return sorted([brd['buildername'] for brd in brdicts])
        return d

    def waitUntilFinished(self):
        return self.status._buildset_waitUntilFinished(self.id)

    def asDict(self):
        d = dict(self.bsdict)
        d["submitted_at"] = str(self.bsdict["submitted_at"])
        return d


class BuildSetSummaryNotifierMixin:

    _buildsetCompleteConsumer = None

    def summarySubscribe(self):
        startConsuming = self.master.mq.startConsuming
        self._buildsetCompleteConsumer = yield startConsuming(
            self._buildsetComplete,
            ('buildsets', None, 'complete'))

    def summaryUnsubscribe(self):
        if self._buildsetCompleteConsumer is not None:
            self._buildsetCompleteConsumer.stopConsuming()
            self._buildsetCompleteConsumer = None

    def sendBuildSetSummary(self, buildset, builds):
        raise NotImplementedError

    @defer.inlineCallbacks
    def _buildsetComplete(self, key, msg):
        bsid = msg['bsid']

        # first, just get the buildset and all build requests for our buildset
        # id
        dl = [self.master.db.buildsets.getBuildset(bsid=bsid),
              self.master.db.buildrequests.getBuildRequests(bsid=bsid)]
        (buildset, breqs) = yield defer.gatherResults(dl)

        # next, get the bdictlist for each build request
        dl = []
        for breq in breqs:
            d = self.master.db.builds.getBuilds(
                buildrequestid=breq['buildrequestid'])
            dl.append(d)

        buildinfo = yield defer.gatherResults(dl)

        # next, get the builder for each build request, and for each bdict,
        # look up the actual build object, using the bdictlist retrieved above
        builds = []
        for (breq, bdictlist) in zip(breqs, buildinfo):
            builder = self.master_status.getBuilder(breq['buildername'])
            for bdict in bdictlist:
                build = builder.getBuild(bdict['number'])
                if build is not None:
                    builds.append(build)

        if builds:
            # We've received all of the information about the builds in this
            # buildset; now send out the summary
            self.sendBuildSetSummary(buildset, builds)
