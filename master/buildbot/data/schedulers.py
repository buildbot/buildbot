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
from buildbot.data import masters
from buildbot.data import types
from buildbot.db.schedulers import SchedulerAlreadyClaimedError


class Db2DataMixin(object):

    @defer.inlineCallbacks
    def db2data(self, dbdict):
        master = None
        if dbdict['masterid'] is not None:
            master = yield self.master.data.get(
                ('masters', dbdict['masterid']))
        data = {
            'schedulerid': dbdict['id'],
            'name': dbdict['name'],
            'enabled': dbdict['enabled'],
            'master': master,
        }
        defer.returnValue(data)


class SchedulerEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /schedulers/n:schedulerid
        /masters/n:masterid/schedulers/n:schedulerid
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        dbdict = yield self.master.db.schedulers.getScheduler(
            kwargs['schedulerid'])
        if 'masterid' in kwargs:
            if dbdict['masterid'] != kwargs['masterid']:
                return
        defer.returnValue((yield self.db2data(dbdict))
                          if dbdict else None)

    @defer.inlineCallbacks
    def control(self, action, args, kwargs):
        if action == 'enable':
            schedulerid = kwargs['schedulerid']
            v = args['enabled']
            yield self.master.data.updates.schedulerEnable(schedulerid, v)
        defer.returnValue(None)


class SchedulersEndpoint(Db2DataMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /schedulers
        /masters/n:masterid/schedulers
    """
    rootLinkName = 'schedulers'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        schedulers = yield self.master.db.schedulers.getSchedulers(
            masterid=kwargs.get('masterid'))
        schdicts = yield defer.DeferredList(
            [self.db2data(schdict) for schdict in schedulers],
            consumeErrors=True, fireOnOneErrback=True)
        defer.returnValue([r for (s, r) in schdicts])


class Scheduler(base.ResourceType):

    name = "scheduler"
    plural = "schedulers"
    endpoints = [SchedulerEndpoint, SchedulersEndpoint]
    keyFields = ['schedulerid']
    eventPathPatterns = """
        /schedulers/:schedulerid
    """

    class EntityType(types.Entity):
        schedulerid = types.Integer()
        name = types.String()
        enabled = types.Boolean()
        master = types.NoneOk(masters.Master.entityType)
    entityType = EntityType(name)

    @defer.inlineCallbacks
    def generateEvent(self, schedulerid, event):
        scheduler = yield self.master.data.get(('schedulers', str(schedulerid)))
        self.produceEvent(scheduler, event)

    @base.updateMethod
    @defer.inlineCallbacks
    def schedulerEnable(self, schedulerid, v):
        yield self.master.db.schedulers.enable(schedulerid, v)
        yield self.generateEvent(schedulerid, 'updated')
        defer.returnValue(None)

    @base.updateMethod
    def findSchedulerId(self, name):
        return self.master.db.schedulers.findSchedulerId(name)

    @base.updateMethod
    def trySetSchedulerMaster(self, schedulerid, masterid):
        d = self.master.db.schedulers.setSchedulerMaster(
            schedulerid, masterid)

        # set is successful: deferred result is True
        d.addCallback(lambda _: True)

        @d.addErrback
        def trapAlreadyClaimedError(why):
            # the db layer throws an exception if the claim fails; we squash
            # that error but let other exceptions continue upward
            why.trap(SchedulerAlreadyClaimedError)

            # set failed: deferred result is False
            return False

        return d

    @defer.inlineCallbacks
    def _masterDeactivated(self, masterid):
        schedulers = yield self.master.db.schedulers.getSchedulers(
            masterid=masterid)
        for sch in schedulers:
            yield self.master.db.schedulers.setSchedulerMaster(sch['id'], None)
