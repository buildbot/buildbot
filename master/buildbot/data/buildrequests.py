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

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import types
from buildbot.db.buildrequests import AlreadyClaimedError
from buildbot.db.buildrequests import NotClaimedError
from buildbot.process.results import RETRY

if TYPE_CHECKING:
    import datetime
    from typing import Sequence

    from buildbot.data.resultspec import ResultSpec
    from buildbot.db.buildrequests import BuildRequestModel


def _db2data(dbmodel: BuildRequestModel, properties: dict | None):
    return {
        'buildrequestid': dbmodel.buildrequestid,
        'buildsetid': dbmodel.buildsetid,
        'builderid': dbmodel.builderid,
        'priority': dbmodel.priority,
        'claimed': dbmodel.claimed,
        'claimed_at': dbmodel.claimed_at,
        'claimed_by_masterid': dbmodel.claimed_by_masterid,
        'complete': dbmodel.complete,
        'results': dbmodel.results,
        'submitted_at': dbmodel.submitted_at,
        'complete_at': dbmodel.complete_at,
        'waited_for': dbmodel.waited_for,
        'properties': properties,
    }


def _generate_filtered_properties(props: dict, filters: Sequence) -> dict | None:
    """
    This method returns Build's properties according to property filters.

    :param props: Properties as a dict (from db)
    :param filters: Desired properties keys as a list (from API URI)
    """
    # by default no properties are returned
    if not props and not filters:
        return None

    set_filters = set(filters)
    if '*' in set_filters:
        return props

    return {k: v for k, v in props.items() if k in set_filters}


buildrequests_field_mapping = {
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


@defer.inlineCallbacks
def _get_buildset_properties_filtered(master, buildsetid: int, filters: Sequence):
    if not filters:
        return None

    props = yield master.db.buildsets.getBuildsetProperties(buildsetid)
    return _generate_filtered_properties(props, filters)


class BuildRequestEndpoint(base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/buildrequests/n:buildrequestid",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec: ResultSpec, kwargs):
        buildrequest = yield self.master.db.buildrequests.getBuildRequest(kwargs['buildrequestid'])
        if not buildrequest:
            return None

        filters = resultSpec.popProperties() if hasattr(resultSpec, 'popProperties') else []
        properties = yield _get_buildset_properties_filtered(
            self.master, buildrequest.buildsetid, filters
        )
        return _db2data(buildrequest, properties)

    @defer.inlineCallbacks
    def set_request_priority(self, brid, args, kwargs):
        priority = args['priority']
        yield self.master.db.buildrequests.set_build_requests_priority(
            brids=[brid], priority=priority
        )

    @defer.inlineCallbacks
    def control(self, action, args, kwargs):
        brid = kwargs['buildrequestid']
        if action == "cancel":
            self.master.mq.produce(
                ('control', 'buildrequests', str(brid), 'cancel'),
                {'reason': args.get('reason', 'no reason')},
            )
        elif action == "set_priority":
            yield self.set_request_priority(brid, args, kwargs)
        else:
            raise ValueError(f"action: {action} is not supported")


class BuildRequestsEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = [
        "/buildrequests",
        "/builders/n:builderid/buildrequests",
    ]
    rootLinkName = 'buildrequests'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        builderid = kwargs.get("builderid", None)
        complete = resultSpec.popBooleanFilter('complete')
        claimed_by_masterid = resultSpec.popBooleanFilter('claimed_by_masterid')
        if claimed_by_masterid:
            # claimed_by_masterid takes precedence over 'claimed' filter
            # (no need to check consistency with 'claimed' filter even if
            # 'claimed'=False with 'claimed_by_masterid' set, doesn't make sense)
            claimed = claimed_by_masterid
        else:
            claimed = resultSpec.popBooleanFilter('claimed')

        bsid = resultSpec.popOneFilter('buildsetid', 'eq')
        resultSpec.fieldMapping = buildrequests_field_mapping
        buildrequests = yield self.master.db.buildrequests.getBuildRequests(
            builderid=builderid,
            complete=complete,
            claimed=claimed,
            bsid=bsid,
            resultSpec=resultSpec,
        )
        results = []
        filters = resultSpec.popProperties() if hasattr(resultSpec, 'popProperties') else []
        for br in buildrequests:
            properties = yield _get_buildset_properties_filtered(
                self.master, br.buildsetid, filters
            )
            results.append(_db2data(br, properties))
        return results


class BuildRequest(base.ResourceType):
    name = "buildrequest"
    plural = "buildrequests"
    endpoints = [BuildRequestEndpoint, BuildRequestsEndpoint]
    eventPathPatterns = [
        "/buildsets/:buildsetid/builders/:builderid/buildrequests/:buildrequestid",
        "/buildrequests/:buildrequestid",
        "/builders/:builderid/buildrequests/:buildrequestid",
    ]

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
        properties = types.NoneOk(types.SourcedProperties())

    entityType = EntityType(name)

    @defer.inlineCallbacks
    def generateEvent(self, brids, event):
        events = []
        for brid in brids:
            # get the build and munge the result for the notification
            br = yield self.master.data.get(('buildrequests', str(brid)))
            events.append(br)
        for br in events:
            self.produceEvent(br, event)

    @defer.inlineCallbacks
    def callDbBuildRequests(self, brids, db_callable, event, **kw):
        if not brids:
            # empty buildrequest list. No need to call db API
            return True
        try:
            yield db_callable(brids, **kw)
        except AlreadyClaimedError:
            # the db layer returned an AlreadyClaimedError exception, usually
            # because one of the buildrequests has already been claimed by
            # another master
            return False
        yield self.generateEvent(brids, event)
        return True

    @base.updateMethod
    def claimBuildRequests(self, brids: list[int], claimed_at: datetime.datetime | None = None):
        return self.callDbBuildRequests(
            brids,
            self.master.db.buildrequests.claimBuildRequests,
            event="claimed",
            claimed_at=claimed_at,
        )

    @base.updateMethod
    @defer.inlineCallbacks
    def unclaimBuildRequests(self, brids: list[int]):
        if brids:
            yield self.master.db.buildrequests.unclaimBuildRequests(brids)
            yield self.generateEvent(brids, "unclaimed")

    @base.updateMethod
    @defer.inlineCallbacks
    def completeBuildRequests(
        self, brids: list[int], results: int, complete_at: datetime.datetime | None = None
    ):
        assert results != RETRY, "a buildrequest cannot be completed with a retry status!"
        if not brids:
            # empty buildrequest list. No need to call db API
            return True
        try:
            yield self.master.db.buildrequests.completeBuildRequests(
                brids, results, complete_at=complete_at
            )
        except NotClaimedError:
            # the db layer returned a NotClaimedError exception, usually
            # because one of the buildrequests has been claimed by another
            # master
            return False
        yield self.generateEvent(brids, "complete")

        # check for completed buildsets -- one call for each build request with
        # a unique bsid
        seen_bsids = set()
        for brid in brids:
            brdict = yield self.master.db.buildrequests.getBuildRequest(brid)

            if brdict:
                bsid = brdict.buildsetid
                if bsid in seen_bsids:
                    continue
                seen_bsids.add(bsid)
                yield self.master.data.updates.maybeBuildsetComplete(bsid)

        return True

    @base.updateMethod
    @defer.inlineCallbacks
    def rebuildBuildrequest(self, buildrequest: dict[str, Any]):
        # goal is to make a copy of the original buildset
        buildset = yield self.master.data.get(('buildsets', buildrequest['buildsetid']))
        properties = yield self.master.data.get((
            'buildsets',
            buildrequest['buildsetid'],
            'properties',
        ))
        # use original build id: after rebuild, it is saved in new buildset `rebuilt_buildid` column
        builds = yield self.master.data.get((
            'buildrequests',
            buildrequest['buildrequestid'],
            'builds',
        ))
        # if already rebuilt build of the same initial build is rebuilt again only save the build
        # id of the initial build
        if len(builds) != 0 and buildset['rebuilt_buildid'] is None:
            rebuilt_buildid = builds[0]['buildid']
        else:
            rebuilt_buildid = buildset['rebuilt_buildid']

        ssids = [ss['ssid'] for ss in buildset['sourcestamps']]
        res = yield self.master.data.updates.addBuildset(
            waited_for=False,
            scheduler='rebuild',
            sourcestamps=ssids,
            reason='rebuild',
            properties=properties,
            builderids=[buildrequest['builderid']],
            external_idstring=buildset['external_idstring'],
            rebuilt_buildid=rebuilt_buildid,
            parent_buildid=buildset['parent_buildid'],
            parent_relationship=buildset['parent_relationship'],
        )
        return res
