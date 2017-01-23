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
from twisted.python import log
from zope.interface import implementer

from buildbot import interfaces
from buildbot.util.eventual import eventually


@implementer(interfaces.IBuildRequestStatus)
class BuildRequestStatus:

    def __init__(self, buildername, brid, status, brdict=None):
        self.buildername = buildername
        self.brid = brid
        self.status = status
        self.master = status.master

        self._brdict = brdict
        self._buildrequest = None
        self._buildrequest_lock = defer.DeferredLock()

    @defer.inlineCallbacks
    def _getBuildRequest(self):
        """
        Get the underlying BuildRequest object for this status.  This is a slow
        operation!

        @returns: BuildRequest instance or None, via Deferred
        """
        # late binding to avoid an import cycle
        from buildbot.process import buildrequest

        # this is only set once, so no need to lock if we already have it
        if self._buildrequest:
            defer.returnValue(self._buildrequest)
            return

        yield self._buildrequest_lock.acquire()

        try:
            if not self._buildrequest:
                if self._brdict is None:
                    self._brdict = (
                        yield self.master.db.buildrequests.getBuildRequest(
                            self.brid))

                br = yield buildrequest.BuildRequest.fromBrdict(self.master,
                                                                self._brdict)
                self._buildrequest = br
        finally:
            self._buildrequest_lock.release()

        self._buildrequest_lock.release()

        defer.returnValue(self._buildrequest)

    def buildStarted(self, build):
        self.status._buildrequest_buildStarted(build.status)
        self.builds.append(build.status)

    # methods called by our clients
    @defer.inlineCallbacks
    def getBsid(self):
        br = yield self._getBuildRequest()
        defer.returnValue(br.bsid)

    @defer.inlineCallbacks
    def getBuildProperties(self):
        br = yield self._getBuildRequest()
        defer.returnValue(br.properties)

    def getSourceStamp(self):
        # TODO..
        return defer.succeed(None)

    def getBuilderName(self):
        return self.buildername

    @defer.inlineCallbacks
    def getBuilds(self):
        builder = self.status.getBuilder(self.getBuilderName())
        builds = []

        bdicts = yield self.master.db.builds.getBuilds(buildrequestid=self.brid)

        buildnums = sorted([bdict['number'] for bdict in bdicts])

        for buildnum in buildnums:
            bs = builder.getBuild(buildnum)
            if bs:
                builds.append(bs)
        defer.returnValue(builds)

    def subscribe(self, observer):
        d = self.getBuilds()

        @d.addCallback
        def notify_old(oldbuilds):
            for bs in oldbuilds:
                eventually(observer, bs)
        d.addCallback(lambda _:
                      self.status._buildrequest_subscribe(self.brid, observer))
        d.addErrback(log.err, 'while notifying subscribers')

    def unsubscribe(self, observer):
        self.status._buildrequest_unsubscribe(self.brid, observer)

    @defer.inlineCallbacks
    def getSubmitTime(self):
        br = yield self._getBuildRequest()
        defer.returnValue(br.submittedAt)

    def asDict(self):
        result = {}
        # Constant
        result['source'] = None  # not available sync, sorry
        result['builderName'] = self.buildername
        result['submittedAt'] = None  # not available sync, sorry

        # Transient
        result['builds'] = []  # not available async, sorry
        return result

    @defer.inlineCallbacks
    def asDict_async(self):
        result = {}

        ss = yield self.getSourceStamp()
        result['source'] = ss.asDict()
        props = yield self.getBuildProperties()
        result['properties'] = props.asList()
        result['builderName'] = self.getBuilderName()
        result['submittedAt'] = yield self.getSubmitTime()

        builds = yield self.getBuilds()
        result['builds'] = [build.asDict() for build in builds]

        defer.returnValue(result)
