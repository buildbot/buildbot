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

from buildbot import interfaces
from buildbot.data import resultspec
from buildbot.db import buildrequests
from buildbot.process import properties
from buildbot.status.results import FAILURE
from buildbot.status.results import SKIPPED
from twisted.internet import defer
from twisted.python import log
from zope.interface import implements


class BuildRequestCollapser(object):
    # brids is a list of the new added buildrequests id
    # This class is called before generated the 'new' event for the buildrequest

    # Before adding new buildset/buildrequests, we must examine each unclaimed
    # buildrequest.
    # EG:
    #  1. get the list of all unclaimed buildrequests:
    #     - We must exclude all buildsets which have at least 1 claimed buildrequest
    #  2. For each unclaimed buildrequests, if compatible with the new request
    #     (sourcestamps match, except for revision) Then:
    #     2.1. claim it
    #     2.2. complete it with result SKIPPED

    def __init__(self, master, brids):
        self.master = master
        self.brids = brids

    @defer.inlineCallbacks
    def _getUnclaimedBRDicts(self, builderid):
        # As soon as a buildset contains at least one claimed buildRequest, then it's too late
        # to collapse other buildRequests of this buildset.
        claim_brdicts = yield self.master.data.get(('builders',
                                                    builderid,
                                                    'buildrequests'),
                                                   [resultspec.Filter('claimed',
                                                                      'eq',
                                                                      [True])])
        ign_buildSetIDs = [brdict['buildsetid'] for brdict in claim_brdicts]

        # Retrieve the list of Brdicts for all unclaimed builds which "can" be collapsed
        unclaim_brdicts = yield self.master.data.get(('builders',
                                                      builderid,
                                                      'buildrequests'),
                                                     [resultspec.Filter('claimed',
                                                                        'eq',
                                                                        [False]),
                                                      resultspec.Filter('buildsetid',
                                                                        'ne',
                                                                        ign_buildSetIDs)])
        # sort by submitted_at, so the first is the oldest
        unclaim_brdicts.sort(key=lambda brd: brd['submitted_at'])
        defer.returnValue(unclaim_brdicts)

    @defer.inlineCallbacks
    def collapse(self):
        collapseBRs = []

        for brid in self.brids:
            # Get the BuildRequest object
            brdict = yield self.master.data.get(('buildrequests', brid))
            # Retreive the buildername
            builderid = brdict['builderid']
            bldrdict = yield self.master.data.get(('builders', builderid))
            # Get the builder object
            bldr = self.master.botmaster.builders.get(bldrdict['name'])
            # Get the Collapse BuildRequest function (from the configuration)
            collapseRequestsFn = bldr.getCollapseRequestsFn() if bldr else None
            unclaim_brDicts = yield self._getUnclaimedBRDicts(builderid)

            # short circuit if there is no merging to do
            if not collapseRequestsFn or not unclaim_brDicts:
                continue

            for unclaim_brDict in unclaim_brDicts:
                if unclaim_brDict['buildrequestid'] == brdict['buildrequestid']:
                    continue

                canCollapse = yield collapseRequestsFn(bldr, brdict, unclaim_brDict)

                if canCollapse is True:
                    collapseBRs.append(unclaim_brDict)

        brids = [brDict['buildrequestid'] for brDict in collapseBRs]
        if collapseBRs:
            bsids = list(set([brDict['buildsetid'] for brDict in collapseBRs]))
            # Claim the buildrequests
            yield self.master.data.updates.claimBuildRequests(brids)
            # complete the buildrequest with result SKIPPED.
            yield self.master.data.updates.completeBuildRequests(brids,
                                                                 SKIPPED)
            for bsid in bsids:
                # Buildset will be complete with result=SKIPPED
                yield self.master.data.updates.maybeBuildsetComplete(bsid)
        defer.returnValue(brids)


class TempSourceStamp(object):
    # temporary fake sourcestamp; attributes are added below

    def asDict(self):
        # This return value should match the kwargs to SourceStampsConnectorComponent.findSourceStampId
        result = vars(self).copy()

        del result['ssid']
        del result['changes']

        if 'patch' in result and result['patch'] is None:
            result['patch'] = (None, None, None)
        result['patch_level'], result['patch_body'], result['patch_subdir'] = result.pop('patch')
        result['patch_author'], result['patch_comment'] = result.pop('patch_info')

        assert all(
            isinstance(val, (unicode, type(None), int))
            for attr, val in result.items()
        ), result
        return result


class BuildRequest(object):

    """

    A rolled-up encapsulation of all of the data relevant to a build request.

    This class is used by the C{nextBuild} and C{collapseRequests} configuration
    parameters, as well as in starting a build.  Construction of a BuildRequest
    object is a heavyweight process involving a lot of database queries, so
    it should be avoided where possible.  See bug #1894.

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

    submittedAt = None
    sources = {}

    @classmethod
    def fromBrdict(cls, master, brdict):
        """
        Construct a new L{BuildRequest} from a dictionary as returned by
        L{BuildRequestsConnectorComponent.getBuildRequest}.

        This method uses a cache, which may result in return of stale objects;
        for the most up-to-date information, use the database connector
        methods.

        @param master: current build master
        @param brdict: build request dictionary

        @returns: L{BuildRequest}, via Deferred
        """
        cache = master.caches.get_cache("BuildRequests", cls._make_br)
        return cache.get(brdict['buildrequestid'], brdict=brdict, master=master)

    @classmethod
    @defer.inlineCallbacks
    def _make_br(cls, brid, brdict, master):
        buildrequest = cls()
        buildrequest.id = brid
        buildrequest.bsid = brdict['buildsetid']
        builder = yield master.db.builders.getBuilder(brdict['builderid'])
        buildrequest.buildername = builder['name']
        buildrequest.builderid = brdict['builderid']
        buildrequest.priority = brdict['priority']
        dt = brdict['submitted_at']
        buildrequest.submittedAt = dt and calendar.timegm(dt.utctimetuple())
        buildrequest.master = master
        buildrequest.waitedFor = brdict['waited_for']

        # fetch the buildset to get the reason
        buildset = yield master.db.buildsets.getBuildset(brdict['buildsetid'])
        assert buildset  # schema should guarantee this
        buildrequest.reason = buildset['reason']

        # fetch the buildset properties, and convert to Properties
        buildset_properties = yield master.db.buildsets.getBuildsetProperties(brdict['buildsetid'])

        buildrequest.properties = properties.Properties.fromDict(buildset_properties)

        # make a fake sources dict (temporary)
        bsdata = yield master.data.get(('buildsets', str(buildrequest.bsid)))
        assert bsdata['sourcestamps'], "buildset must have at least one sourcestamp"
        buildrequest.sources = {}
        for ssdata in bsdata['sourcestamps']:
            ss = buildrequest.sources[ssdata['codebase']] = TempSourceStamp()
            ss.ssid = ssdata['ssid']
            ss.branch = ssdata['branch']
            ss.revision = ssdata['revision']
            ss.repository = ssdata['repository']
            ss.project = ssdata['project']
            ss.codebase = ssdata['codebase']
            if ssdata['patch']:
                patch = ssdata['patch']
                ss.patch = (patch['level'], patch['body'], patch['subdir'])
                ss.patch_info = (patch['author'], patch['comment'])
            else:
                ss.patch = None
                ss.patch_info = (None, None)
            ss.changes = []
            # XXX: sourcestamps don't have changes anymore; this affects merging!!

        defer.returnValue(buildrequest)

    @staticmethod
    @defer.inlineCallbacks
    def canBeCollapsed(master, brdict1, brdict2):
        """
        Returns true if both buildrequest can be merged, via Deferred.

        This implements Buildbot's default collapse strategy.
        """
        # short-circuit: if these are for the same buildset, collapse away
        if brdict1['buildsetid'] == brdict2['buildsetid']:
            defer.returnValue(True)
            return

        # get the buidlsets for each buildrequest
        selfBuildsets = yield master.data.get(
            ('buildsets', str(brdict1['buildsetid'])))
        otherBuildsets = yield master.data.get(
            ('buildsets', str(brdict2['buildsetid'])))

        # extract sourcestamps, as dictionaries by codebase
        selfSources = dict((ss['codebase'], ss)
                           for ss in selfBuildsets['sourcestamps'])
        otherSources = dict((ss['codebase'], ss)
                            for ss in otherBuildsets['sourcestamps'])

        # if the sets of codebases do not match, we can't collapse
        if set(selfSources) != set(otherSources):
            defer.returnValue(False)
            return

        for c, selfSS in selfSources.iteritems():
            otherSS = otherSources[c]
            if selfSS['revision'] != otherSS['revision']:
                defer.returnValue(False)
                return
            if selfSS['repository'] != otherSS['repository']:
                defer.returnValue(False)
                return
            if selfSS['branch'] != otherSS['branch']:
                defer.returnValue(False)
                return
            if selfSS['project'] != otherSS['project']:
                defer.returnValue(False)
                return
            # anything with a patch won't be collapsed
            if selfSS['patch'] or otherSS['patch']:
                defer.returnValue(False)
                return

        defer.returnValue(True)

    def mergeSourceStampsWith(self, others):
        """ Returns one merged sourcestamp for every codebase """
        # get all codebases from all requests
        all_codebases = set(self.sources.iterkeys())
        for other in others:
            all_codebases |= set(other.sources.iterkeys())

        all_merged_sources = {}
        # walk along the codebases
        for codebase in all_codebases:
            all_sources = []
            if codebase in self.sources:
                all_sources.append(self.sources[codebase])
            for other in others:
                if codebase in other.sources:
                    all_sources.append(other.sources[codebase])
            assert len(all_sources) > 0, "each codebase should have atleast one sourcestamp"

            # TODO: select the sourcestamp that best represents the merge,
            # preferably the latest one.  This used to be accomplished by
            # looking at changeids and picking the highest-numbered.
            all_merged_sources[codebase] = all_sources[-1]

        return [source for source in all_merged_sources.itervalues()]

    def mergeReasons(self, others):
        """Return a reason for the merged build request."""
        reasons = []
        for req in [self] + others:
            if req.reason and req.reason not in reasons:
                reasons.append(req.reason)
        return ", ".join(reasons)

    def getSubmitTime(self):
        return self.submittedAt

    @defer.inlineCallbacks
    def cancelBuildRequest(self):
        # first, try to claim the request; if this fails, then it's too late to
        # cancel the build anyway
        try:
            yield self.master.data.updates.claimBuildRequests([self.id])
        except buildrequests.AlreadyClaimedError:
            log.msg("build request already claimed; cannot cancel")
            return

        # send a cancellation message
        builderid = -1  # TODO
        key = ('buildrequests', self.bsid, builderid, self.id, 'cancelled')
        msg = dict(
            brid=self.id,
            bsid=self.bsid,
            buildername=self.buildername,
            builderid=builderid)
        self.master.mq.produce(key, msg)

        # then complete it with 'FAILURE'; this is the closest we can get to
        # cancelling a request without running into trouble with dangling
        # references.
        yield self.master.data.updates.completeBuildRequests([self.id],
                                                             FAILURE)

        # and see if the enclosing buildset may be complete
        yield self.master.data.updates.maybeBuildsetComplete(self.bsid)


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
        d = self.original_request.cancelBuildRequest()
        d.addErrback(log.err, 'while cancelling build request')
