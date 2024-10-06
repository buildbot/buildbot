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
from buildbot.db.logs import LogSlugExistsError
from buildbot.util import identifiers

if TYPE_CHECKING:
    from buildbot.db.logs import LogModel


class EndpointMixin:
    def db2data(self, model: LogModel):
        data = {
            'logid': model.id,
            'name': model.name,
            'slug': model.slug,
            'stepid': model.stepid,
            'complete': model.complete,
            'num_lines': model.num_lines,
            'type': model.type,
        }
        return defer.succeed(data)


class LogEndpoint(EndpointMixin, base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = """
        /logs/n:logid
        /steps/n:stepid/logs/i:log_slug
        /builds/n:buildid/steps/i:step_name/logs/i:log_slug
        /builds/n:buildid/steps/n:step_number/logs/i:log_slug
        /builders/n:builderid/builds/n:build_number/steps/i:step_name/logs/i:log_slug
        /builders/n:builderid/builds/n:build_number/steps/n:step_number/logs/i:log_slug
        /builders/s:buildername/builds/n:build_number/steps/i:step_name/logs/i:log_slug
        /builders/s:buildername/builds/n:build_number/steps/n:step_number/logs/i:log_slug
    """

    async def get(self, resultSpec, kwargs):
        if 'logid' in kwargs:
            dbdict = await self.master.db.logs.getLog(kwargs['logid'])
            return (yield self.db2data(dbdict)) if dbdict else None

        retriever = base.NestedBuildDataRetriever(self.master, kwargs)
        step_dict = await retriever.get_step_dict()
        if step_dict is None:
            return None

        dbdict = await self.master.db.logs.getLogBySlug(step_dict.id, kwargs.get('log_slug'))
        return (yield self.db2data(dbdict)) if dbdict else None


class LogsEndpoint(EndpointMixin, base.BuildNestingMixin, base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = """
        /steps/n:stepid/logs
        /builds/n:buildid/steps/i:step_name/logs
        /builds/n:buildid/steps/n:step_number/logs
        /builders/n:builderid/builds/n:build_number/steps/i:step_name/logs
        /builders/n:builderid/builds/n:build_number/steps/n:step_number/logs
        /builders/s:buildername/builds/n:build_number/steps/i:step_name/logs
        /builders/s:buildername/builds/n:build_number/steps/n:step_number/logs
    """

    async def get(self, resultSpec, kwargs):
        retriever = base.NestedBuildDataRetriever(self.master, kwargs)
        step_dict = await retriever.get_step_dict()
        if step_dict is None:
            return []
        logs = await self.master.db.logs.getLogs(stepid=step_dict.id)
        results = []
        for dbdict in logs:
            results.append((yield self.db2data(dbdict)))
        return results


class Log(base.ResourceType):
    name = "log"
    plural = "logs"
    endpoints = [LogEndpoint, LogsEndpoint]
    keyField = "logid"
    eventPathPatterns = """
        /logs/:logid
        /steps/:stepid/logs/:slug
    """
    subresources = ["LogChunk"]

    class EntityType(types.Entity):
        logid = types.Integer()
        name = types.String()
        slug = types.Identifier(50)
        stepid = types.Integer()
        complete = types.Boolean()
        num_lines = types.Integer()
        type = types.Identifier(1)

    entityType = EntityType(name, 'Log')

    async def generateEvent(self, _id, event):
        # get the build and munge the result for the notification
        build = await self.master.data.get(('logs', str(_id)))
        self.produceEvent(build, event)

    @base.updateMethod
    async def addLog(self, stepid, name, type):
        slug = identifiers.forceIdentifier(50, name)
        while True:
            try:
                logid = await self.master.db.logs.addLog(
                    stepid=stepid, name=name, slug=slug, type=type
                )
            except LogSlugExistsError:
                slug = identifiers.incrementIdentifier(50, slug)
                continue
            self.generateEvent(logid, "new")
            return logid

    @base.updateMethod
    async def appendLog(self, logid, content):
        res = await self.master.db.logs.appendLog(logid=logid, content=content)
        self.generateEvent(logid, "append")
        return res

    @base.updateMethod
    async def finishLog(self, logid):
        res = await self.master.db.logs.finishLog(logid=logid)
        self.generateEvent(logid, "finished")
        return res

    @base.updateMethod
    def compressLog(self, logid):
        return self.master.db.logs.compressLog(logid=logid)
