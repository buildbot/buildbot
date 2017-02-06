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

from buildbot.data import base
from buildbot.data import types
from buildbot.util import identifiers


class EndpointMixin(object):

    def db2data(self, dbdict):
        data = {
            'logid': dbdict['id'],
            'name': dbdict['name'],
            'slug': dbdict['slug'],
            'stepid': dbdict['stepid'],
            'complete': dbdict['complete'],
            'num_lines': dbdict['num_lines'],
            'type': dbdict['type'],
        }
        return defer.succeed(data)


class LogEndpoint(EndpointMixin, base.BuildNestingMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /logs/n:logid
        /steps/n:stepid/logs/i:log_slug
        /builds/n:buildid/steps/i:step_name/logs/i:log_slug
        /builds/n:buildid/steps/n:step_number/logs/i:log_slug
        /builders/n:builderid/builds/n:build_number/steps/i:step_name/logs/i:log_slug
        /builders/n:builderid/builds/n:build_number/steps/n:step_number/logs/i:log_slug
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        if 'logid' in kwargs:
            dbdict = yield self.master.db.logs.getLog(kwargs['logid'])
            defer.returnValue((yield self.db2data(dbdict))
                              if dbdict else None)
            return

        stepid = yield self.getStepid(kwargs)
        if stepid is None:
            return

        dbdict = yield self.master.db.logs.getLogBySlug(stepid,
                                                        kwargs.get('log_slug'))
        defer.returnValue((yield self.db2data(dbdict))
                          if dbdict else None)


class LogsEndpoint(EndpointMixin, base.BuildNestingMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /steps/n:stepid/logs
        /builds/n:buildid/steps/i:step_name/logs
        /builds/n:buildid/steps/n:step_number/logs
        /builders/n:builderid/builds/n:build_number/steps/i:step_name/logs
        /builders/n:builderid/builds/n:build_number/steps/n:step_number/logs
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        stepid = yield self.getStepid(kwargs)
        if not stepid:
            defer.returnValue([])
            return
        logs = yield self.master.db.logs.getLogs(stepid=stepid)
        results = []
        for dbdict in logs:
            results.append((yield self.db2data(dbdict)))
        defer.returnValue(results)


class Log(base.ResourceType):

    name = "log"
    plural = "logs"
    endpoints = [LogEndpoint, LogsEndpoint]
    keyFields = ['stepid', 'logid']
    eventPathPatterns = """
        /logs/:logid
        /steps/:stepid/logs/:slug
    """

    class EntityType(types.Entity):
        logid = types.Integer()
        name = types.String()
        slug = types.Identifier(50)
        stepid = types.Integer()
        complete = types.Boolean()
        num_lines = types.Integer()
        type = types.Identifier(1)
    entityType = EntityType(name)

    @defer.inlineCallbacks
    def generateEvent(self, _id, event):
        # get the build and munge the result for the notification
        build = yield self.master.data.get(('logs', str(_id)))
        self.produceEvent(build, event)

    @base.updateMethod
    @defer.inlineCallbacks
    def addLog(self, stepid, name, type):
        slug = identifiers.forceIdentifier(50, name)
        while True:
            try:
                logid = yield self.master.db.logs.addLog(
                    stepid=stepid, name=name, slug=slug, type=type)
            except KeyError:
                slug = identifiers.incrementIdentifier(50, slug)
                continue
            self.generateEvent(logid, "new")
            defer.returnValue(logid)

    @base.updateMethod
    @defer.inlineCallbacks
    def appendLog(self, logid, content):
        res = yield self.master.db.logs.appendLog(logid=logid, content=content)
        self.generateEvent(logid, "append")
        defer.returnValue(res)

    @base.updateMethod
    @defer.inlineCallbacks
    def finishLog(self, logid):
        res = yield self.master.db.logs.finishLog(logid=logid)
        self.generateEvent(logid, "finished")
        defer.returnValue(res)

    @base.updateMethod
    def compressLog(self, logid):
        return self.master.db.logs.compressLog(logid=logid)
