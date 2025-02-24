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

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import masters
from buildbot.data import types
from buildbot.db.changesources import ChangeSourceAlreadyClaimedError

if TYPE_CHECKING:
    from buildbot.db.changesources import ChangeSourceModel
    from buildbot.util.twisted import InlineCallbacksType


@defer.inlineCallbacks
def _db2data(master, dbdict: ChangeSourceModel):
    dbmaster = None
    if dbdict.masterid is not None:
        dbmaster = yield master.data.get(('masters', dbdict.masterid))
    data = {
        'changesourceid': dbdict.id,
        'name': dbdict.name,
        'master': dbmaster,
    }
    return data


class ChangeSourceEndpoint(base.Endpoint):
    pathPatterns = [
        "/changesources/n:changesourceid",
        "/masters/n:masterid/changesources/n:changesourceid",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        dbdict = yield self.master.db.changesources.getChangeSource(kwargs['changesourceid'])
        if 'masterid' in kwargs:
            if dbdict.masterid != kwargs['masterid']:
                return None
        return (yield _db2data(self.master, dbdict)) if dbdict else None
        return (yield _db2data(self.master, dbdict)) if dbdict else None


class ChangeSourcesEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = [
        "/changesources",
        "/masters/n:masterid/changesources",
    ]
    rootLinkName = 'changesources'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        changesources = yield self.master.db.changesources.getChangeSources(
            masterid=kwargs.get('masterid')
        )
        csdicts = yield defer.DeferredList(
            [_db2data(self.master, cs) for cs in changesources],
            consumeErrors=True,
            fireOnOneErrback=True,
        )
        return [r for (s, r) in csdicts]


class ChangeSource(base.ResourceType):
    name = "changesource"
    plural = "changesources"
    endpoints = [ChangeSourceEndpoint, ChangeSourcesEndpoint]

    class EntityType(types.Entity):
        changesourceid = types.Integer()
        name = types.String()
        master = types.NoneOk(masters.Master.entityType)

    entityType = EntityType(name)

    @base.updateMethod
    def findChangeSourceId(self, name: str) -> defer.Deferred[int]:
        return self.master.db.changesources.findChangeSourceId(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def trySetChangeSourceMaster(
        self, changesourceid: int, masterid: int
    ) -> InlineCallbacksType[bool]:
        # the db layer throws an exception if the claim fails; we translate
        # that to a straight true-false value. We could trap the exception
        # type, but that seems a bit too restrictive
        try:
            yield self.master.db.changesources.setChangeSourceMaster(changesourceid, masterid)
        except ChangeSourceAlreadyClaimedError:
            return False
        return True

    @defer.inlineCallbacks
    def _masterDeactivated(self, masterid):
        changesources = yield self.master.db.changesources.getChangeSources(masterid=masterid)
        for cs in changesources:
            yield self.master.db.changesources.setChangeSourceMaster(cs.id, None)
