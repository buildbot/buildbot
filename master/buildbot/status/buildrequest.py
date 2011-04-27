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
from twisted.internet import defer
from buildbot import interfaces
from buildbot.process import buildrequest
from buildbot.util.eventual import eventually

class BuildRequestStatus:
    implements(interfaces.IBuildRequestStatus)

    def __init__(self, buildername, brid, status):
        self.buildername = buildername
        self.brid = brid
        self.status = status
        self.master = status.master

        self._buildrequest = None
        self._buildrequest_lock = defer.DeferredLock()

    @defer.deferredGenerator
    def _getBuildRequest(self):
        """
        Get the underlying BuildRequest object for this status.  This is a slow
        operation!

        @returns: BuildRequest instance or None, via Deferred
        """
        # this is only set once, so no need to lock if we already have it
        if self._buildrequest:
            yield self._buildrequest

        wfd = defer.waitForDeferred(
                self._buildrequest_lock.acquire())
        yield wfd
        wfd.getResult()

        try:
            if not self._buildrequest:
                wfd = defer.waitForDeferred(
                    self.master.db.buildrequests.getBuildRequest(self.brid))
                yield wfd
                brd = wfd.getResult()

                wfd = defer.waitForDeferred(
                    buildrequest.BuildRequest.fromBrdict(self.master, brd))
                yield wfd
                self._buildrequest = wfd.getResult()
        except: # try/finally isn't allowed in generators in older Pythons
            self._buildrequest_lock.release()
            raise

        self._buildrequest_lock.release()

        yield self._buildrequest

    def buildStarted(self, build):
        self.status._buildrequest_buildStarted(build.status)
        self.builds.append(build.status)

    # methods called by our clients
    @defer.deferredGenerator
    def getSourceStamp(self):
        wfd = defer.waitForDeferred(
                self._getBuildRequest())
        yield wfd
        br = wfd.getResult()

        yield br.source

    def getBuilderName(self):
        return self.buildername

    def getBuilds(self):
        builder = self.status.getBuilder(self.getBuilderName())
        builds = []
        buildnums = sorted(self.master.db.get_buildnums_for_brid(self.brid))
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

    @defer.deferredGenerator
    def getSubmitTime(self):
        wfd = defer.waitForDeferred(
                self._getBuildRequest())
        yield wfd
        br = wfd.getResult()

        yield br.submittedAt

    def asDict(self):
        result = {}
        # Constant
        result['source'] = None # not available sync, sorry
        result['builderName'] = self.buildername
        result['submittedAt'] = None # not availably sync, sorry

        # Transient
        result['builds'] = [build.asDict() for build in self.getBuilds()]
        return result

    @defer.deferredGenerator
    def asDict_async(self):
        result = {}

        wfd = defer.waitForDeferred(
                self.getSourceStamp())
        yield wfd
        ss = wfd.getResult()
        result['source'] = ss.asDict()

        result['builderName'] = self.getBuilderName()

        wfd = defer.waitForDeferred(
                self.getSubmitTime())
        yield wfd
        submittedAt = wfd.getResult()
        result['submittedAt'] = submittedAt

        result['builds'] = [ build.asDict() for build in self.getBuilds() ]

        yield result
