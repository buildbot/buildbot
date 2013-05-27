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

from twisted.internet import defer
from buildbot.data import base, types
from buildbot.util import datetime2epoch

class Db2DataMixin(object):

    def db2data(self, dbdict):
        data = {
            'stepid': dbdict['id'],
            'number': dbdict['number'],
            'name': dbdict['name'],
            'buildid' : dbdict['buildid'],
            'build_link': base.Link(('build', str(dbdict['buildid']))),
            'started_at': datetime2epoch(dbdict['started_at']),
            'complete': dbdict['complete_at'] is not None,
            'complete_at': datetime2epoch(dbdict['complete_at']),
            'state_strings': dbdict['state_strings'],
            'results': dbdict['results'],
            'urls': dbdict['urls'],
            'link': base.Link(('build', str(dbdict['id']))),
        }
        return defer.succeed(data)


class StepEndpoint(Db2DataMixin, base.BuildNestingMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /step/n:stepid
        /build/n:buildid/step/i:step_name
        /build/n:buildid/step/n:step_number
        /builder/n:builderid/build/n:build_number/step/i:step_name
        /builder/n:builderid/build/n:build_number/step/n:step_number
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        if 'stepid' in kwargs:
            dbdict = yield self.master.db.steps.getStep(kwargs['stepid'])
            defer.returnValue((yield self.db2data(dbdict))
                                if dbdict else None)
            return

        buildid = yield self.getBuildid(kwargs)
        if buildid is None:
            return

        dbdict = yield self.master.db.steps.getStepByBuild(buildid=buildid,
                number=kwargs.get('step_number'), name=kwargs.get('step_name'))
        defer.returnValue((yield self.db2data(dbdict))
                            if dbdict else None)


class StepsEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /build/n:buildid/step
        /builder/n:builderid/build/n:build_number/step
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        if 'buildid' in kwargs:
            buildid = kwargs['buildid']
        else:
            build = self.master.db.builds.getBuildByNumber(
                builderid=kwargs['builderid'], number=kwargs['build_number'])
            if not build:
                return
            buildid = build['id']
        steps = yield self.master.db.steps.getSteps(buildid=buildid)
        defer.returnValue([ (yield self.db2data(dbdict)) for dbdict in steps ])


class Step(base.ResourceType):

    name = "step"
    plural = "steps"
    endpoints = [ StepEndpoint, StepsEndpoint ]
    keyFields = [ 'builderid', 'stepid' ]

    class EntityType(types.Entity):
        stepid = types.Integer()
        number = types.Integer()
        name = types.Identifier(50)
        buildid = types.Integer()
        build_link = types.Link()
        started_at = types.Integer()
        complete = types.Boolean()
        complete_at = types.NoneOk(types.Integer())
        results = types.NoneOk(types.Integer())
        state_strings = types.List(of=types.String())
        urls = types.List(of=types.String())
        link = types.Link()
    entityType = EntityType(name)

    @base.updateMethod
    def newStep(self, buildid, name):
        return self.master.db.steps.addStep(
                buildid=buildid, name=name, state_strings=['starting'])

    @base.updateMethod
    def setStepStateStrings(self, stepid, state_strings):
        return self.master.db.steps.setStepStateStrings(
                stepid=stepid, state_strings=state_strings)

    @base.updateMethod
    def finishStep(self, stepid, results):
        return self.master.db.steps.finishStep(
                stepid=stepid, results=results)
