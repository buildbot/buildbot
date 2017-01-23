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
from twisted.internet import reactor
from twisted.python import log

from buildbot.data import base
from buildbot.data import resultspec
from buildbot.data import types
from buildbot.process.results import RETRY
from buildbot.util import epoch2datetime

# time, in minutes, after which a master that hasn't checked in will be
# marked as inactive
EXPIRE_MINUTES = 10


def _db2data(master):
    return dict(masterid=master['id'],
                name=master['name'],
                active=master['active'],
                last_active=master['last_active'])


class MasterEndpoint(base.Endpoint):

    isCollection = False
    pathPatterns = """
        /masters/n:masterid
        /builders/n:builderid/masters/n:masterid
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        # if a builder is given, only return the master if it's associated with
        # this builder
        if 'builderid' in kwargs:
            builder = yield self.master.db.builders.getBuilder(
                builderid=kwargs['builderid'])
            if not builder or kwargs['masterid'] not in builder['masterids']:
                defer.returnValue(None)
                return
        m = yield self.master.db.masters.getMaster(kwargs['masterid'])
        defer.returnValue(_db2data(m) if m else None)


class MastersEndpoint(base.Endpoint):

    isCollection = True
    pathPatterns = """
        /masters
        /builders/n:builderid/masters
    """
    rootLinkName = 'masters'

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        masterlist = yield self.master.db.masters.getMasters()
        if 'builderid' in kwargs:
            builder = yield self.master.db.builders.getBuilder(
                builderid=kwargs['builderid'])
            if builder:
                masterids = set(builder['masterids'])
                masterlist = [m for m in masterlist if m['id'] in masterids]
            else:
                masterlist = []
        defer.returnValue([_db2data(m) for m in masterlist])


class Master(base.ResourceType):

    name = "master"
    plural = "masters"
    endpoints = [MasterEndpoint, MastersEndpoint]
    eventPathPatterns = """
        /masters/:masterid
    """

    class EntityType(types.Entity):
        masterid = types.Integer()
        name = types.String()
        active = types.Boolean()
        last_active = types.DateTime()
    entityType = EntityType(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def masterActive(self, name, masterid, _reactor=reactor):
        activated = yield self.master.db.masters.setMasterState(
            masterid=masterid, active=True, _reactor=_reactor)
        if activated:
            self.produceEvent(
                dict(masterid=masterid, name=name, active=True),
                'started')

    @base.updateMethod
    @defer.inlineCallbacks
    def expireMasters(self, forceHouseKeeping=False, _reactor=reactor):
        too_old = epoch2datetime(_reactor.seconds() - 60 * EXPIRE_MINUTES)
        masters = yield self.master.db.masters.getMasters()
        for m in masters:
            if m['last_active'] is not None and m['last_active'] >= too_old:
                continue

            # mark the master inactive, and send a message on its behalf
            deactivated = yield self.master.db.masters.setMasterState(
                masterid=m['id'], active=False, _reactor=_reactor)
            if deactivated:
                yield self._masterDeactivated(m['id'], m['name'])
            elif forceHouseKeeping:
                yield self._masterDeactivatedHousekeeping(m['id'], m['name'])

    @base.updateMethod
    @defer.inlineCallbacks
    def masterStopped(self, name, masterid):
        deactivated = yield self.master.db.masters.setMasterState(
            masterid=masterid, active=False)
        if deactivated:
            yield self._masterDeactivated(masterid, name)

    @defer.inlineCallbacks
    def _masterDeactivatedHousekeeping(self, masterid, name):
        log.msg("doing housekeeping for master %d %s" % (masterid, name))

        # common code for deactivating a master
        yield self.master.data.rtypes.worker._masterDeactivated(
            masterid=masterid)
        yield self.master.data.rtypes.builder._masterDeactivated(
            masterid=masterid)
        yield self.master.data.rtypes.scheduler._masterDeactivated(
            masterid=masterid)
        yield self.master.data.rtypes.changesource._masterDeactivated(
            masterid=masterid)

        # for each build running on that instance..
        builds = yield self.master.data.get(('builds',),
                                            filters=[resultspec.Filter('masterid', 'eq', [masterid]),
                                                     resultspec.Filter('complete', 'eq', [False])])
        for build in builds:
            # stop any running steps..
            steps = yield self.master.data.get(
                ('builds', build['buildid'], 'steps'),
                filters=[resultspec.Filter('results', 'eq', [None])])
            for step in steps:
                # finish remaining logs for those steps..
                logs = yield self.master.data.get(
                    ('steps', step['stepid'], 'logs'),
                    filters=[resultspec.Filter('complete', 'eq',
                                               [False])])
                for _log in logs:
                    yield self.master.data.updates.finishLog(
                        logid=_log['logid'])
                yield self.master.data.updates.finishStep(
                    stepid=step['stepid'], results=RETRY, hidden=False)
            # then stop the build itself
            yield self.master.data.updates.finishBuild(
                buildid=build['buildid'], results=RETRY)

        # unclaim all of the build requests owned by the deactivated instance
        buildrequests = yield self.master.db.buildrequests.getBuildRequests(
            complete=False, claimed=masterid)
        yield self.master.db.buildrequests.unclaimBuildRequests(
            brids=[br['buildrequestid'] for br in buildrequests])

    @defer.inlineCallbacks
    def _masterDeactivated(self, masterid, name):
        yield self._masterDeactivatedHousekeeping(masterid, name)

        self.produceEvent(
            dict(masterid=masterid, name=name, active=False),
            'stopped')
