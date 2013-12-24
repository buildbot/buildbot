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

from buildbot.data import base
from buildbot.data import types
from buildbot.util import identifiers
from twisted.internet import defer


class EndpointMixin(object):

    def db2data(self, dbdict):
        data = {
            'logid': dbdict['id'],
            'name': dbdict['name'],
            'slug': dbdict['slug'],
            'stepid': dbdict['stepid'],
            'step_link': base.Link(('step', str(dbdict['stepid']))),
            'complete': dbdict['complete'],
            'num_lines': dbdict['num_lines'],
            'type': dbdict['type'],
            'link': base.Link(('log', str(dbdict['id']))),
        }
        return defer.succeed(data)


class LogEndpoint(EndpointMixin, base.BuildNestingMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /log/n:logid
        /step/n:stepid/log/i:log_slug
        /build/n:buildid/step/i:step_name/log/i:log_slug
        /build/n:buildid/step/n:step_number/log/i:log_slug
        /builder/n:builderid/build/n:build_number/step/i:step_name/log/i:log_slug
        /builder/n:builderid/build/n:build_number/step/n:step_number/log/i:log_slug
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
        /step/n:stepid/log
        /build/n:buildid/step/i:step_name/log
        /build/n:buildid/step/n:step_number/log
        /builder/n:builderid/build/n:build_number/step/i:step_name/log
        /builder/n:builderid/build/n:build_number/step/n:step_number/log
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        stepid = yield self.getStepid(kwargs)
        if not stepid:
            defer.returnValue([])
            return
        logs = yield self.master.db.logs.getLogs(stepid=stepid)
        defer.returnValue([(yield self.db2data(dbdict)) for dbdict in logs])


class Log(base.ResourceType):

    name = "log"
    plural = "logs"
    endpoints = [LogEndpoint, LogsEndpoint]
    keyFields = ['stepid', 'logid']

    class EntityType(types.Entity):
        logid = types.Integer()
        name = types.String()
        slug = types.Identifier(50)
        stepid = types.Integer()
        step_link = types.Link()
        complete = types.Boolean()
        num_lines = types.Integer()
        type = types.Identifier(1)
        link = types.Link()
    entityType = EntityType(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def newLog(self, stepid, name, type):
        slug = name
        while True:
            try:
                logid = yield self.master.db.logs.addLog(
                    stepid=stepid, name=name, slug=slug, type=type)
            except KeyError:
                slug = identifiers.incrementIdentifier(50, slug)
                continue
            defer.returnValue(logid)

    @base.updateMethod
    def finishLog(self, logid):
        return self.master.db.logs.finishLog(logid=logid)

    @base.updateMethod
    def compressLog(self, logid):
        return self.master.db.logs.compressLog(logid=logid)
