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
from twisted.internet import defer


class Db2DataMixin(object):

    def db2data(self, dbdict):
        data = {
            'stepid': dbdict['id'],
            'number': dbdict['number'],
            'name': dbdict['name'],
            'buildid': dbdict['buildid'],
            'build_link': base.Link(('builds', str(dbdict['buildid']))),
            'started_at': dbdict['started_at'],
            'complete': dbdict['complete_at'] is not None,
            'complete_at': dbdict['complete_at'],
            'state_strings': dbdict['state_strings'],
            'results': dbdict['results'],
            'urls': dbdict['urls'],
            'link': base.Link(('builds', str(dbdict['id']))),
        }
        return defer.succeed(data)


class StepEndpoint(Db2DataMixin, base.BuildNestingMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /steps/n:stepid
        /builds/n:buildid/steps/i:step_name
        /builds/n:buildid/steps/n:step_number
        /builders/n:builderid/builds/n:build_number/steps/i:step_name
        /builders/n:builderid/builds/n:build_number/steps/n:step_number
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
        dbdict = yield self.master.db.steps.getStep(
            buildid=buildid,
            number=kwargs.get('step_number'),
            name=kwargs.get('step_name'))
        defer.returnValue((yield self.db2data(dbdict))
                          if dbdict else None)


class StepsEndpoint(Db2DataMixin, base.BuildNestingMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /builds/n:buildid/steps
        /builders/n:builderid/builds/n:build_number/steps
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        if 'buildid' in kwargs:
            buildid = kwargs['buildid']
        else:
            buildid = yield self.getBuildid(kwargs)
            if buildid is None:
                return
        steps = yield self.master.db.steps.getSteps(buildid=buildid)
        defer.returnValue([(yield self.db2data(dbdict)) for dbdict in steps])

    def startConsuming(self, callback, options, kwargs):
        if 'stepid' in kwargs:
            return self.master.mq.startConsuming(
                callback,
                ('steps', str(kwargs['stepid']), None))
        elif 'buildid' in kwargs:
            return self.master.mq.startConsuming(
                callback,
                ('builds', str(kwargs['buildid']), 'steps', None, None))
        else:
            raise NotImplementedError("cannot consume from this path")


class Step(base.ResourceType):

    name = "step"
    plural = "steps"
    endpoints = [StepEndpoint, StepsEndpoint]
    keyFields = ['builderid', 'stepid']
    eventPathPatterns = """
        /builds/:buildid/steps/:stepid
        /steps/:stepid
    """

    class EntityType(types.Entity):
        stepid = types.Integer()
        number = types.Integer()
        name = types.Identifier(50)
        buildid = types.Integer()
        build_link = types.Link()
        started_at = types.NoneOk(types.DateTime())
        complete = types.Boolean()
        complete_at = types.NoneOk(types.DateTime())
        results = types.NoneOk(types.Integer())
        state_strings = types.List(of=types.String())
        urls = types.List(of=types.String())
        link = types.Link()
    entityType = EntityType(name)

    @defer.inlineCallbacks
    def generateEvent(self, stepid, event):
        step = yield self.master.data.get(('steps', stepid))
        self.produceEvent(step, event)

    @base.updateMethod
    @defer.inlineCallbacks
    def newStep(self, buildid, name):
        stepid, num, name = yield self.master.db.steps.addStep(
            buildid=buildid, name=name, state_strings=[u'pending'])
        yield self.generateEvent(stepid, 'new')
        defer.returnValue((stepid, num, name))

    @base.updateMethod
    @defer.inlineCallbacks
    def startStep(self, stepid):
        yield self.master.db.steps.startStep(stepid=stepid)
        yield self.generateEvent(stepid, 'started')

    @base.updateMethod
    @defer.inlineCallbacks
    def setStepStateStrings(self, stepid, state_strings):
        yield self.master.db.steps.setStepStateStrings(
            stepid=stepid, state_strings=state_strings)
        yield self.generateEvent(stepid, 'updated')

    @base.updateMethod
    @defer.inlineCallbacks
    def finishStep(self, stepid, results):
        yield self.master.db.steps.finishStep(
            stepid=stepid, results=results)
        yield self.generateEvent(stepid, 'finished')
