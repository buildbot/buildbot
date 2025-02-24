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
    from buildbot.db.steps import StepModel
    from buildbot.util.twisted import InlineCallbacksType


def _db2data(model: StepModel):
    return {
        'stepid': model.id,
        'number': model.number,
        'name': model.name,
        'buildid': model.buildid,
        'started_at': model.started_at,
        "locks_acquired_at": model.locks_acquired_at,
        'complete': model.complete_at is not None,
        'complete_at': model.complete_at,
        'state_string': model.state_string,
        'results': model.results,
        'urls': [{'name': item.name, 'url': item.url} for item in model.urls],
        'hidden': model.hidden,
    }


class StepEndpoint(base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/steps/n:stepid",
        "/builds/n:buildid/steps/i:step_name",
        "/builds/n:buildid/steps/n:step_number",
        "/builders/n:builderid/builds/n:build_number/steps/i:step_name",
        "/builders/n:builderid/builds/n:build_number/steps/n:step_number",
        "/builders/s:buildername/builds/n:build_number/steps/i:step_name",
        "/builders/s:buildername/builds/n:build_number/steps/n:step_number",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        if 'stepid' in kwargs:
            dbdict = yield self.master.db.steps.getStep(kwargs['stepid'])
            return _db2data(dbdict) if dbdict else None
        buildid = yield self.getBuildid(kwargs)
        if buildid is None:
            return None
        dbdict = yield self.master.db.steps.getStep(
            buildid=buildid, number=kwargs.get('step_number'), name=kwargs.get('step_name')
        )
        return _db2data(dbdict) if dbdict else None


class StepsEndpoint(base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = [
        "/builds/n:buildid/steps",
        "/builders/n:builderid/builds/n:build_number/steps",
        "/builders/s:buildername/builds/n:build_number/steps",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        if 'buildid' in kwargs:
            buildid = kwargs['buildid']
        else:
            buildid = yield self.getBuildid(kwargs)
            if buildid is None:
                return None
        steps = yield self.master.db.steps.getSteps(buildid=buildid)
        return [_db2data(model) for model in steps]


class UrlEntityType(types.Entity):
    name = types.String()
    url = types.String()


class Step(base.ResourceType):
    name = "step"
    plural = "steps"
    endpoints = [StepEndpoint, StepsEndpoint]
    eventPathPatterns = [
        "/builds/:buildid/steps/:stepid",
        "/steps/:stepid",
    ]

    class EntityType(types.Entity):
        stepid = types.Integer()
        number = types.Integer()
        name = types.Identifier(50)
        buildid = types.Integer()
        started_at = types.NoneOk(types.DateTime())
        locks_acquired_at = types.NoneOk(types.DateTime())
        complete = types.Boolean()
        complete_at = types.NoneOk(types.DateTime())
        results = types.NoneOk(types.Integer())
        state_string = types.String()
        urls = types.List(of=UrlEntityType("Url"))
        hidden = types.Boolean()

    entityType = EntityType(name)

    @defer.inlineCallbacks
    def generateEvent(self, stepid, event):
        step = yield self.master.data.get(('steps', stepid))
        self.produceEvent(step, event)

    @base.updateMethod
    @defer.inlineCallbacks
    def addStep(self, buildid, name):
        stepid, num, name = yield self.master.db.steps.addStep(
            buildid=buildid, name=name, state_string='pending'
        )
        yield self.generateEvent(stepid, 'new')
        return (stepid, num, name)

    @base.updateMethod
    @defer.inlineCallbacks
    def startStep(self, stepid: int, started_at: int | None = None, locks_acquired: bool = False):
        if started_at is None:
            started_at = int(self.master.reactor.seconds())
        yield self.master.db.steps.startStep(
            stepid=stepid, started_at=started_at, locks_acquired=locks_acquired
        )
        yield self.generateEvent(stepid, 'started')

    @base.updateMethod
    @defer.inlineCallbacks
    def set_step_locks_acquired_at(self, stepid: int, locks_acquired_at: int | None = None):
        if locks_acquired_at is None:
            locks_acquired_at = int(self.master.reactor.seconds())

        yield self.master.db.steps.set_step_locks_acquired_at(
            stepid=stepid, locks_acquired_at=locks_acquired_at
        )
        yield self.generateEvent(stepid, 'updated')

    @base.updateMethod
    @defer.inlineCallbacks
    def setStepStateString(self, stepid: int, state_string: str) -> InlineCallbacksType[None]:
        yield self.master.db.steps.setStepStateString(stepid=stepid, state_string=state_string)
        yield self.generateEvent(stepid, 'updated')

    @base.updateMethod
    @defer.inlineCallbacks
    def addStepURL(self, stepid: int, name: str, url: str) -> InlineCallbacksType[None]:
        yield self.master.db.steps.addURL(stepid=stepid, name=name, url=url)
        yield self.generateEvent(stepid, 'updated')

    @base.updateMethod
    @defer.inlineCallbacks
    def finishStep(self, stepid: int, results: int, hidden: bool) -> InlineCallbacksType[None]:
        yield self.master.db.steps.finishStep(stepid=stepid, results=results, hidden=hidden)
        yield self.generateEvent(stepid, 'finished')
