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

import copy
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.python import log

from buildbot.data import base
from buildbot.data import sourcestamps as sourcestampsapi
from buildbot.data import types
from buildbot.db.buildsets import AlreadyCompleteError
from buildbot.process.buildrequest import BuildRequestCollapser
from buildbot.process.results import SUCCESS
from buildbot.process.results import worst_status
from buildbot.util import datetime2epoch
from buildbot.util import epoch2datetime

if TYPE_CHECKING:
    from buildbot.db.buildsets import BuildSetModel


@defer.inlineCallbacks
def _db2data(model: BuildSetModel | None, master):
    if not model:
        return None

    buildset = {
        "bsid": model.bsid,
        "external_idstring": model.external_idstring,
        "reason": model.reason,
        "submitted_at": datetime2epoch(model.submitted_at),
        "complete": model.complete,
        "complete_at": datetime2epoch(model.complete_at),
        "results": model.results,
        "parent_buildid": model.parent_buildid,
        "parent_relationship": model.parent_relationship,
        "rebuilt_buildid": model.rebuilt_buildid,
    }

    # gather the actual sourcestamps, in parallel
    sourcestamps = []

    @defer.inlineCallbacks
    def getSs(ssid):
        ss = yield master.data.get(('sourcestamps', str(ssid)))
        sourcestamps.append(ss)

    yield defer.DeferredList(
        [getSs(id) for id in model.sourcestamps], fireOnOneErrback=True, consumeErrors=True
    )

    buildset['sourcestamps'] = sourcestamps
    return buildset


buildset_field_mapping = {
    'bsid': 'buildsets.id',
    'external_idstring': 'buildsets.external_idstring',
    'reason': 'buildsets.reason',
    'rebuilt_buildid': 'buildsets.rebuilt_buildid',
    'submitted_at': 'buildsets.submitted_at',
    'complete': 'buildsets.complete',
    'complete_at': 'buildsets.complete_at',
    'results': 'buildsets.results',
    'parent_buildid': 'buildsets.parent_buildid',
    'parent_relationship': 'buildsets.parent_relationship',
}


class BuildsetEndpoint(base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/buildsets/n:bsid",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        res = yield self.master.db.buildsets.getBuildset(kwargs['bsid'])
        res = yield _db2data(res, self.master)
        return res


class BuildsetsEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = [
        "/buildsets",
    ]
    rootLinkName = 'buildsets'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        complete = resultSpec.popBooleanFilter('complete')
        resultSpec.fieldMapping = buildset_field_mapping
        buildsets = yield self.master.db.buildsets.getBuildsets(
            complete=complete, resultSpec=resultSpec
        )

        buildsets = yield defer.gatherResults(
            [_db2data(bs, self.master) for bs in buildsets], consumeErrors=True
        )

        return buildsets


class Buildset(base.ResourceType):
    name = "buildset"
    plural = "buildsets"
    endpoints = [BuildsetEndpoint, BuildsetsEndpoint]
    eventPathPatterns = [
        "/buildsets/:bsid",
    ]

    class EntityType(types.Entity):
        bsid = types.Integer()
        external_idstring = types.NoneOk(types.String())
        reason = types.String()
        rebuilt_buildid = types.NoneOk(types.Integer())
        submitted_at = types.Integer()
        complete = types.Boolean()
        complete_at = types.NoneOk(types.Integer())
        results = types.NoneOk(types.Integer())
        sourcestamps = types.List(of=sourcestampsapi.SourceStamp.entityType)
        parent_buildid = types.NoneOk(types.Integer())
        parent_relationship = types.NoneOk(types.String())

    entityType = EntityType(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def addBuildset(
        self,
        waited_for: bool,
        scheduler: str | None = None,
        sourcestamps: list[dict[str, Any] | str] | None = None,
        reason: str = '',
        properties: dict[str, Any] | None = None,
        builderids: list[int] | None = None,
        external_idstring: str | None = None,
        rebuilt_buildid: int | None = None,
        parent_buildid: int | None = None,
        parent_relationship: str | None = None,
        priority=0,
    ):
        if sourcestamps is None:
            sourcestamps = []
        if properties is None:
            properties = {}
        if builderids is None:
            builderids = []
        submitted_at = int(self.master.reactor.seconds())
        bsid, brids = yield self.master.db.buildsets.addBuildset(
            sourcestamps=sourcestamps,
            reason=reason,
            rebuilt_buildid=rebuilt_buildid,
            properties=properties,
            builderids=builderids,
            waited_for=waited_for,
            external_idstring=external_idstring,
            submitted_at=epoch2datetime(submitted_at),
            parent_buildid=parent_buildid,
            parent_relationship=parent_relationship,
            priority=priority,
        )

        yield BuildRequestCollapser(self.master, list(brids.values())).collapse()

        # get each of the sourcestamps for this buildset (sequentially)
        bsdict = yield self.master.db.buildsets.getBuildset(bsid)
        sourcestamps = []
        for ssid in bsdict.sourcestamps:
            sourcestamps.append((yield self.master.data.get(('sourcestamps', str(ssid)))).copy())

        # notify about the component build requests
        brResource = self.master.data.getResourceType("buildrequest")
        brResource.generateEvent(list(brids.values()), 'new')

        # and the buildset itself
        msg = {
            "bsid": bsid,
            "external_idstring": external_idstring,
            "reason": reason,
            "parent_buildid": parent_buildid,
            "rebuilt_buildid": rebuilt_buildid,
            "submitted_at": submitted_at,
            "complete": False,
            "complete_at": None,
            "results": None,
            "scheduler": scheduler,
            "sourcestamps": sourcestamps,
        }
        # TODO: properties=properties)
        self.produceEvent(msg, "new")

        log.msg(f"added buildset {bsid} to database")

        # if there are no builders, then this is done already, so send the
        # appropriate messages for that
        if not builderids:
            yield self.maybeBuildsetComplete(bsid)

        return (bsid, brids)

    @base.updateMethod
    @defer.inlineCallbacks
    def maybeBuildsetComplete(self, bsid: int):
        brdicts = yield self.master.db.buildrequests.getBuildRequests(bsid=bsid, complete=False)

        # if there are incomplete buildrequests, bail out
        if brdicts:
            return

        brdicts = yield self.master.db.buildrequests.getBuildRequests(bsid=bsid)

        # figure out the overall results of the buildset:
        cumulative_results = SUCCESS
        for brdict in brdicts:
            cumulative_results = worst_status(cumulative_results, brdict.results)

        # get a copy of the buildset
        bsdict = yield self.master.db.buildsets.getBuildset(bsid)

        # if it's already completed, we're late to the game, and there's
        # nothing to do.
        #
        # NOTE: there's still a strong possibility of a race condition here,
        # which would cause buildset being completed twice.
        # in this case, the db layer will detect that and raise AlreadyCompleteError
        if bsdict.complete:
            return

        # mark it as completed in the database
        complete_at = epoch2datetime(int(self.master.reactor.seconds()))
        try:
            yield self.master.db.buildsets.completeBuildset(
                bsid, cumulative_results, complete_at=complete_at
            )
        except AlreadyCompleteError:
            return
        # get the sourcestamps for the message
        # get each of the sourcestamps for this buildset (sequentially)
        bsdict = yield self.master.db.buildsets.getBuildset(bsid)
        sourcestamps = []
        for ssid in bsdict.sourcestamps:
            sourcestamps.append(
                copy.deepcopy((yield self.master.data.get(('sourcestamps', str(ssid)))))
            )

        msg = {
            "bsid": bsid,
            "external_idstring": bsdict.external_idstring,
            "reason": bsdict.reason,
            "rebuilt_buildid": bsdict.rebuilt_buildid,
            "sourcestamps": sourcestamps,
            "submitted_at": bsdict.submitted_at,
            "complete": True,
            "complete_at": complete_at,
            "results": cumulative_results,
            "parent_buildid": bsdict.parent_buildid,
            "parent_relationship": bsdict.parent_relationship,
        }
        # TODO: properties=properties)
        self.produceEvent(msg, "complete")
