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
from buildbot.schedulers import forcesched
from buildbot.www.rest import JSONRPC_CODES
from buildbot.www.rest import BadJsonRpc2

if TYPE_CHECKING:
    from buildbot.data.resultspec import ResultSpec
    from buildbot.util.twisted import InlineCallbacksType


def forceScheduler2Data(sched: forcesched.ForceScheduler) -> dict[str, Any]:
    ret = {
        "all_fields": [],
        "name": str(sched.name),
        "button_name": str(sched.buttonName),
        "label": str(sched.label),
        "builder_names": [str(name) for name in sched.builderNames],
        "enabled": sched.enabled,
    }
    ret["all_fields"] = [field.getSpec() for field in sched.all_fields]
    return ret


class ForceSchedulerEndpoint(base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/forceschedulers/i:schedulername",
    ]

    def findForceScheduler(
        self, schedulername: str
    ) -> defer.Deferred[forcesched.ForceScheduler] | None:
        # eventually this may be db backed. This is why the API is async
        for sched in self.master.allSchedulers():
            if sched.name == schedulername and isinstance(sched, forcesched.ForceScheduler):
                return defer.succeed(sched)
        return None

    @defer.inlineCallbacks
    def get(
        self, resultSpec: ResultSpec, kwargs: dict[str, Any]
    ) -> InlineCallbacksType[dict[str, Any] | None]:
        sched = yield self.findForceScheduler(kwargs['schedulername'])
        if sched is not None:
            return forceScheduler2Data(sched)
        return None

    @defer.inlineCallbacks
    def control(self, action: str, args: Any, kwargs: Any) -> InlineCallbacksType[Any]:
        if action == "force":
            sched = yield self.findForceScheduler(kwargs['schedulername'])
            if "owner" not in args:
                args['owner'] = "user"
            try:
                res = yield sched.force(**args)
                return res
            except forcesched.CollectedValidationError as e:
                raise BadJsonRpc2(e.errors, JSONRPC_CODES["invalid_params"]) from e  # type: ignore[arg-type]
        return None


class ForceSchedulersEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = [
        "/forceschedulers",
        "/builders/:builderid/forceschedulers",
    ]
    rootLinkName = 'forceschedulers'

    @defer.inlineCallbacks
    def get(
        self, resultSpec: ResultSpec, kwargs: dict[str, Any]
    ) -> InlineCallbacksType[list[dict[str, Any]]]:
        ret = []
        builderid = kwargs.get('builderid', None)
        bdict = None
        if builderid is not None:
            bdict = yield self.master.db.builders.getBuilder(builderid)
        for sched in self.master.allSchedulers():
            if isinstance(sched, forcesched.ForceScheduler):
                if builderid is not None and bdict.name not in sched.builderNames:  # type: ignore[union-attr]
                    continue
                ret.append(forceScheduler2Data(sched))
        return ret


class ForceScheduler(base.ResourceType):
    name = "forcescheduler"
    plural = "forceschedulers"
    endpoints = [ForceSchedulerEndpoint, ForceSchedulersEndpoint]

    class EntityType(types.Entity):
        name = types.Identifier(50)
        button_name = types.String()
        label = types.String()
        builder_names = types.List(of=types.Identifier(50))
        enabled = types.Boolean()
        all_fields = types.List(of=types.JsonObject())

    entityType = EntityType(name)
