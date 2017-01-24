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
from twisted.internet import reactor

from buildbot.data import base
from buildbot.data import types
from buildbot.db.buildrequests import AlreadyClaimedError
from buildbot.db.buildrequests import NotClaimedError
from buildbot.process import results
from buildbot.process.results import RETRY


class Db2DataMixin(object):

    def db2data(self, dbdict):
        data = {
            'buildrequestid': dbdict['buildrequestid'],
            'buildsetid': dbdict['buildsetid'],
            'builderid': dbdict['builderid'],
            'priority': dbdict['priority'],
            'claimed': dbdict['claimed'],
            'claimed_at': dbdict['claimed_at'],
            'claimed_by_masterid': dbdict['claimed_by_masterid'],
            'complete': dbdict['complete'],
            'results': dbdict['results'],
            'submitted_at': dbdict['submitted_at'],
            'complete_at': dbdict['complete_at'],
            'waited_for': dbdict['waited_for'],
        }
        return defer.succeed(data)
    fieldMapping = {
        'buildrequestid': 'buildrequests.id',
        'buildsetid': 'buildrequests.buildsetid',
        'builderid': 'buildrequests.builderid',
        'priority': 'buildrequests.priority',
        'complete': 'buildrequests.complete',
        'results': 'buildrequests.results',
        'submitted_at': 'buildrequests.submitted_at',
        'complete_at': 'buildrequests.complete_at',
        'waited_for': 'buildrequests.waited_for',
        # br claim
        'claimed_at': 'buildrequest_claims.claimed_at',
        'claimed_by_masterid': 'buildrequest_claims.masterid',
    }


class BuildRequestEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /buildrequests/n:buildrequestid
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        buildrequest = yield self.master.db.buildrequests.getBuildRequest(kwargs['buildrequestid'])

        if buildrequest:
            defer.returnValue((yield self.db2data(buildrequest)))
        defer.returnValue(None)

    @defer.inlineCallbacks
    def control(self, action, args, kwargs):
        if action != "cancel":
            raise ValueError("action: {} is not supported".format(action))
        brid = kwargs['buildrequestid']
        # first, try to claim the request; if this fails, then it's too late to
        # cancel the build anyway
        try:
            b = yield self.master.db.buildrequests.claimBuildRequests(brids=[brid])
        except AlreadyClaimedError:
            # XXX race condition
            # - After a buildrequest was claimed, and
            # - Before creating a build,
            # the claiming master still
            # needs to do some processing, (send a message to the message queue,
            # call maybeStartBuild on the related builder).
            # In that case we won't have the related builds here. We don't have
            # an alternative to letting them run without stopping them for now.
            builds = yield self.master.data.get(("buildrequests", brid, "builds"))

            # Don't call the data API here, as the buildrequests might have been
            # taken by another master. We just send the stop message and forget
            # about those.
            mqKwargs = {'reason': kwargs.get('reason', 'no reason')}
            for b in builds:
                self.master.mq.produce(("control", "builds", str(b['buildid']), "stop"),
                                       mqKwargs)
            defer.returnValue(None)

        # then complete it with 'CANCELLED'; this is the closest we can get to
        # cancelling a request without running into trouble with dangling
        # references.
        yield self.master.data.updates.completeBuildRequests([brid],
                                                             results.CANCELLED)


class BuildRequestsEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /buildrequests
        /builders/n:builderid/buildrequests
    """
    rootLinkName = 'buildrequests'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        builderid = kwargs.get("builderid", None)
        complete = resultSpec.popBooleanFilter('complete')
        claimed_by_masterid = resultSpec.popBooleanFilter(
            'claimed_by_masterid')
        if claimed_by_masterid:
            # claimed_by_masterid takes precedence over 'claimed' filter
            # (no need to check consistency with 'claimed' filter even if
            # 'claimed'=False with 'claimed_by_masterid' set, doesn't make sense)
            claimed = claimed_by_masterid
        else:
            claimed = resultSpec.popBooleanFilter('claimed')

        bsid = resultSpec.popOneFilter('buildsetid', 'eq')
        resultSpec.fieldMapping = self.fieldMapping
        buildrequests = yield self.master.db.buildrequests.getBuildRequests(
            builderid=builderid,
            complete=complete,
            claimed=claimed,
            bsid=bsid,
            resultSpec=resultSpec)
        results = []
        for br in buildrequests:
            results.append((yield self.db2data(br)))
        defer.returnValue(results)


class BuildRequest(base.ResourceType):

    name = "buildrequest"
    plural = "buildrequests"
    endpoints = [BuildRequestEndpoint, BuildRequestsEndpoint]
    keyFields = ['buildsetid', 'builderid', 'buildrequestid']
    eventPathPatterns = """
        /buildsets/:buildsetid/builders/:builderid/buildrequests/:buildrequestid
        /buildrequests/:buildrequestid
        /builders/:builderid/buildrequests/:buildrequestid
    """

    class EntityType(types.Entity):
        buildrequestid = types.Integer()
        buildsetid = types.Integer()
        builderid = types.Integer()
        priority = types.Integer()
        claimed = types.Boolean()
        claimed_at = types.NoneOk(types.DateTime())
        claimed_by_masterid = types.NoneOk(types.Integer())
        complete = types.Boolean()
        results = types.NoneOk(types.Integer())
        submitted_at = types.DateTime()
        complete_at = types.NoneOk(types.DateTime())
        waited_for = types.Boolean()
    entityType = EntityType(name)

    @defer.inlineCallbacks
    def generateEvent(self, brids, event):
        for brid in brids:
            # get the build and munge the result for the notification
            br = yield self.master.data.get(('buildrequests', str(brid)))
            self.produceEvent(br, event)

    @defer.inlineCallbacks
    def callDbBuildRequests(self, brids, db_callable, event, **kw):
        if not brids:
            # empty buildrequest list. No need to call db API
            defer.returnValue(True)
        try:
            yield db_callable(brids, **kw)
        except AlreadyClaimedError:
            # the db layer returned an AlreadyClaimedError exception, usually
            # because one of the buildrequests has already been claimed by
            # another master
            defer.returnValue(False)
        yield self.generateEvent(brids, event)
        defer.returnValue(True)

    @base.updateMethod
    def claimBuildRequests(self, brids, claimed_at=None, _reactor=reactor):
        return self.callDbBuildRequests(brids,
                                        self.master.db.buildrequests.claimBuildRequests,
                                        event="claimed",
                                        claimed_at=claimed_at,
                                        _reactor=_reactor)

    @base.updateMethod
    def reclaimBuildRequests(self, brids, _reactor=reactor):
        return self.callDbBuildRequests(brids,
                                        self.master.db.buildrequests.reclaimBuildRequests,
                                        event="update",
                                        _reactor=_reactor)

    @base.updateMethod
    @defer.inlineCallbacks
    def unclaimBuildRequests(self, brids):
        if brids:
            yield self.master.db.buildrequests.unclaimBuildRequests(brids)
            yield self.generateEvent(brids, "unclaimed")

    @base.updateMethod
    @defer.inlineCallbacks
    def completeBuildRequests(self, brids, results, complete_at=None,
                              _reactor=reactor):
        assert results != RETRY, "a buildrequest cannot be completed with a retry status!"
        if not brids:
            # empty buildrequest list. No need to call db API
            defer.returnValue(True)
        try:
            yield self.master.db.buildrequests.completeBuildRequests(
                brids,
                results,
                complete_at=complete_at,
                _reactor=_reactor)
        except NotClaimedError:
            # the db layer returned a NotClaimedError exception, usually
            # because one of the buildrequests has been claimed by another
            # master
            defer.returnValue(False)
        yield self.generateEvent(brids, "complete")

        # check for completed buildsets -- one call for each build request with
        # a unique bsid
        seen_bsids = set()
        for brid in brids:
            brdict = yield self.master.db.buildrequests.getBuildRequest(brid)

            if brdict:
                bsid = brdict['buildsetid']
                if bsid in seen_bsids:
                    continue
                seen_bsids.add(bsid)
                yield self.master.data.updates.maybeBuildsetComplete(bsid)

        defer.returnValue(True)

    @base.updateMethod
    @defer.inlineCallbacks
    def unclaimExpiredRequests(self, old, _reactor=reactor):
        yield self.master.db.buildrequests.unclaimExpiredRequests(old, _reactor=_reactor)

    @base.updateMethod
    @defer.inlineCallbacks
    def rebuildBuildrequest(self, buildrequest):

        # goal is to make a copy of the original buildset
        buildset = yield self.master.data.get(('buildsets', buildrequest['buildsetid']))
        properties = yield self.master.data.get(('buildsets', buildrequest['buildsetid'], 'properties'))
        ssids = [ss['ssid'] for ss in buildset['sourcestamps']]
        res = yield self.master.data.updates.addBuildset(waited_for=False, scheduler=u'rebuild',
                                                         sourcestamps=ssids, reason=u'rebuild',
                                                         properties=properties, builderids=[
                                                             buildrequest['builderid']], external_idstring=buildset['external_idstring'],
                                                         parent_buildid=buildset['parent_buildid'], parent_relationship=buildset[
                                                             'parent_relationship'],
                                                         )
        defer.returnValue(res)
