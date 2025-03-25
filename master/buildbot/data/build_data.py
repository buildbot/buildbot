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
from buildbot.data import types

if TYPE_CHECKING:
    from buildbot.db.build_data import BuildDataModel


def _db2data(model: BuildDataModel):
    return {
        'buildid': model.buildid,
        'name': model.name,
        'value': model.value,
        'length': model.length,
        'source': model.source,
    }


class BuildDatasNoValueEndpoint(base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = [
        "/builders/n:builderid/builds/n:build_number/data",
        "/builders/s:buildername/builds/n:build_number/data",
        "/builds/n:buildid/data",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        buildid = yield self.getBuildid(kwargs)

        build_datadicts = yield self.master.db.build_data.getAllBuildDataNoValues(buildid)

        results = []
        for dbdict in build_datadicts:
            results.append(_db2data(dbdict))
        return results


class BuildDataNoValueEndpoint(base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/builders/n:builderid/builds/n:build_number/data/i:name",
        "/builders/s:buildername/builds/n:build_number/data/i:name",
        "/builds/n:buildid/data/i:name",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        buildid = yield self.getBuildid(kwargs)
        name = kwargs['name']

        build_datadict = yield self.master.db.build_data.getBuildDataNoValue(buildid, name)

        return _db2data(build_datadict) if build_datadict else None


class BuildDataEndpoint(base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.RAW
    pathPatterns = [
        "/builders/n:builderid/builds/n:build_number/data/i:name/value",
        "/builders/s:buildername/builds/n:build_number/data/i:name/value",
        "/builds/n:buildid/data/i:name/value",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        buildid = yield self.getBuildid(kwargs)
        name = kwargs['name']

        dbdict = yield self.master.db.build_data.getBuildData(buildid, name)
        if not dbdict:
            return None

        return {
            'raw': dbdict.value,
            'mime-type': 'application/octet-stream',
            'filename': dbdict.name,
        }


class BuildData(base.ResourceType):
    name = "build_data"
    plural = "build_data"
    endpoints = [BuildDatasNoValueEndpoint, BuildDataNoValueEndpoint, BuildDataEndpoint]

    class EntityType(types.Entity):
        buildid = types.Integer()
        name = types.String()
        length = types.Integer()
        value = types.NoneOk(types.Binary())
        source = types.String()

    entityType = EntityType(name)

    @base.updateMethod
    def setBuildData(
        self, buildid: int, name: str, value: bytes, source: str
    ) -> defer.Deferred[None]:
        # forward deferred directly
        return self.master.db.build_data.setBuildData(buildid, name, value, source)
