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
from buildbot.data import patches
from buildbot.data import types

if TYPE_CHECKING:
    from typing import Any

    from buildbot.db.sourcestamps import SourceStampModel


def _db2data(ss: SourceStampModel):
    data: dict[str, Any] = {
        'ssid': ss.ssid,
        'branch': ss.branch,
        'revision': ss.revision,
        'project': ss.project,
        'repository': ss.repository,
        'codebase': ss.codebase,
        'created_at': ss.created_at,
        'patch': None,
    }
    if ss.patch is not None:
        data['patch'] = {
            'patchid': ss.patch.patchid,
            'level': ss.patch.level,
            'subdir': ss.patch.subdir,
            'author': ss.patch.author,
            'comment': ss.patch.comment,
            'body': ss.patch.body,
        }
    return data


class SourceStampEndpoint(base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/sourcestamps/n:ssid",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        ssdict = yield self.master.db.sourcestamps.getSourceStamp(kwargs['ssid'])
        return _db2data(ssdict) if ssdict else None


class SourceStampsEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = [
        "/sourcestamps",
        "/buildsets/:buildsetid/sourcestamps",
    ]
    rootLinkName = 'sourcestamps'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        buildsetid = kwargs.get("buildsetid")
        if buildsetid is not None:
            sourcestamps = yield self.master.db.sourcestamps.get_sourcestamps_for_buildset(
                buildsetid
            )
        else:
            sourcestamps = yield self.master.db.sourcestamps.getSourceStamps()

        return [_db2data(ssdict) for ssdict in sourcestamps]


class SourceStamp(base.ResourceType):
    name = "sourcestamp"
    plural = "sourcestamps"
    endpoints = [SourceStampEndpoint, SourceStampsEndpoint]

    class EntityType(types.Entity):
        ssid = types.Integer()
        revision = types.NoneOk(types.String())
        branch = types.NoneOk(types.String())
        repository = types.String()
        project = types.String()
        codebase = types.String()
        patch = types.NoneOk(patches.Patch.entityType)
        created_at = types.DateTime()

    entityType = EntityType(name)
