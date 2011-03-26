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

import calendar
from zope.interface import implements
from twisted.internet import defer
from buildbot import interfaces, sourcestamp
from buildbot.process import properties

class BuildRequest(object):
    """

    A rolled-up encapsulation of all of the data relevant to a build request.

    This class is used by the C{nextBuild} and C{mergeRequests} configuration
    parameters, as well as in starting a build.  Construction of a BuildRequest
    object is a heavyweight process involving a lot of database queries, so
    it should be avoided where possible.  See bug #1894.

    Build requests have a SourceStamp which specifies what sources to build.
    This may specify a specific revision of the source tree (so source.branch,
    source.revision, and source.patch are used). The .patch attribute is either
    None or a tuple of (patchlevel, diff), consisting of a number to use in
    'patch -pN', and a unified-format context diff.

    Alternatively, the SourceStamp may specify a set of Changes to be built,
    contained in source.changes. In this case, the requeset may be mergeable
    with other BuildRequests on the same branch.

    @type source: L{buildbot.sourcestamp.SourceStamp}
    @ivar source: the source stamp that this BuildRequest use

    @type reason: string
    @ivar reason: the reason this Build is being requested. Schedulers provide
    this, but for forced builds the user requesting the build will provide a
    string.  It comes from the buildsets table.

    @type properties: L{properties.Properties}
    @ivar properties: properties that should be applied to this build, taken
    from the buildset containing this build request

    @ivar submittedAt: a timestamp (seconds since epoch) when this request was
    submitted to the Builder. This is used by the CVS step to compute a
    checkout timestamp, as well as by the master to prioritize build requests
    from oldest to newest.

    @ivar buildername: name of the requested builder

    @ivar priority: request priority

    @ivar id: build request ID

    @ivar bsid: ID of the parent buildset
    """

    source = None
    submittedAt = None

    @classmethod
    @defer.deferredGenerator
    def fromBrdict(cls, master, brdict):
        """
        Construct a new L{BuildRequest} from a dictionary as returned by
        L{BuildRequestsConnectorComponent.getBuildRequest}.

        @param master: current build master
        @param brdict: build request dictionary

        @returns: L{BuildRequest}, via Deferred
        """
        buildrequest = cls()
        buildrequest.id = brdict['brid']
        buildrequest.bsid = brdict['buildsetid']
        buildrequest.buildername = brdict['buildername']
        buildrequest.priority = brdict['priority']
        dt = brdict['submitted_at']
        buildrequest.submittedAt = dt and calendar.timegm(dt.utctimetuple())

        # fetch the buildset to get the reason
        wfd = defer.waitForDeferred(
            master.db.buildsets.getBuildset(brdict['buildsetid']))
        yield wfd
        buildset = wfd.getResult()
        assert buildset # schema should guarantee this
        buildrequest.reason = buildset['reason']

        # fetch the buildset properties, and convert to Properties
        wfd = defer.waitForDeferred(
            master.db.buildsets.getBuildsetProperties(brdict['buildsetid']))
        yield wfd
        buildset_properties = wfd.getResult()

        pr = properties.Properties()
        for name, (value, source) in buildset_properties.iteritems():
            pr.setProperty(name, value, source)
        buildrequest.properties = pr

        # fetch the sourcestamp dictionary
        wfd = defer.waitForDeferred(
            master.db.sourcestamps.getSourceStamp(buildset['sourcestampid']))
        yield wfd
        ssdict = wfd.getResult()
        assert ssdict # db schema should enforce this anyway

        # and turn it into a SourceStamp
        wfd = defer.waitForDeferred(
            sourcestamp.SourceStamp.fromSsdict(master, ssdict))
        yield wfd
        buildrequest.source = wfd.getResult()

        yield buildrequest # return value

    # TODO: This should die when db.connector.getBuildRequestWithNumber does
    @classmethod
    def oldConstructor(cls, reason, source, builderName, props):
        buildrequest = cls()
        buildrequest.reason = reason
        buildrequest.source = source
        buildrequest.builderName = builderName
        buildrequest.properties = properties.Properties()
        if props:
            buildrequest.properties.updateFromProperties(props)
        return buildrequest

    def canBeMergedWith(self, other):
        return self.source.canBeMergedWith(other.source)

    def mergeWith(self, others):
        return self.source.mergeWith([o.source for o in others])

    def mergeReasons(self, others):
        """Return a reason for the merged build request."""
        reasons = []
        for req in [self] + others:
            if req.reason and req.reason not in reasons:
                reasons.append(req.reason)
        return ", ".join(reasons)

    def getSubmitTime(self):
        return self.submittedAt

class BuildRequestControl:
    implements(interfaces.IBuildRequestControl)

    def __init__(self, builder, request):
        self.original_builder = builder
        self.original_request = request
        self.brid = request.id

    def subscribe(self, observer):
        raise NotImplementedError

    def unsubscribe(self, observer):
        raise NotImplementedError

    def cancel(self):
        self.original_builder.cancelBuildRequest(self.brid)
