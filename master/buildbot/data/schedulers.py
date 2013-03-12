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
from buildbot.data import base

class Db2DataMixin(object):

    @defer.inlineCallbacks
    def db2data(self, dbdict):
        master = None
        if dbdict['masterid'] is not None:
            master = yield self.master.data.get({},
                                    ('master', dbdict['masterid']))
        data = {
            'schedulerid': dbdict['id'],
            'name': dbdict['name'],
            'master': master,
            'link': base.Link(('scheduler', str(dbdict['id']))),
        }
        defer.returnValue(data)


class SchedulerEndpoint(Db2DataMixin, base.Endpoint):

    pathPatterns = """
        /scheduler/i:schedulerid
        /master/i:masterid/scheduler/i:schedulerid
    """

    @defer.inlineCallbacks
    def get(self, options, kwargs):
        dbdict = yield self.master.db.schedulers.getScheduler(
                                                        kwargs['schedulerid'])
        if 'masterid' in kwargs:
            if dbdict['masterid'] != kwargs['masterid']:
                return
        defer.returnValue((yield self.db2data(dbdict))
                                if dbdict else None)


class SchedulersEndpoint(Db2DataMixin, base.Endpoint):

    pathPatterns = """
        /scheduler
        /master/i:masterid/scheduler
    """
    rootLinkName = 'schedulers'

    @defer.inlineCallbacks
    def get(self, options, kwargs):
        schedulers = yield self.master.db.schedulers.getSchedulers(
                                masterid=kwargs.get('masterid'))
        schdicts = yield defer.DeferredList(
                [ self.db2data(schdict) for schdict in schedulers ],
                consumeErrors=True, fireOnOneErrback=True)
        defer.returnValue([ r for (s, r) in schdicts ])

    def startConsuming(self, callback, options, kwargs):
        return self.master.mq.startConsuming(callback,
                ('scheduler', None, None))


class SchedulerResourceType(base.ResourceType):

    type = "scheduler"
    endpoints = [ SchedulerEndpoint, SchedulersEndpoint ]
    keyFields = [ 'schedulerid' ]

    @base.updateMethod
    def findSchedulerId(self, name):
        return self.master.db.schedulers.findSchedulerId(name)

    @base.updateMethod
    def setSchedulerMaster(self, schedulerid, masterid):
        # the db method raises the same exception as documented
        return self.master.db.schedulers.setSchedulerMaster(
                                            schedulerid, masterid)

    @defer.inlineCallbacks
    def _masterDeactivated(self, masterid):
        schedulers = yield self.master.db.schedulers.getSchedulers(
                                masterid=masterid)
        for sch in schedulers:
            yield self.master.db.schedulers.setSchedulerMaster(sch['id'], None)
