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

from twisted.internet import defer, reactor
from buildbot.data import base
from buildbot.util import datetime2epoch, epoch2datetime

# time, in minutes, after which a master that hasn't checked in will be
# marked as inactive
EXPIRE_MINUTES = 10

def _db2data(master):
    return dict(masterid=master['id'],
                name=master['name'],
                active=master['active'],
                last_active=datetime2epoch(master['last_active']),
                link=base.Link(('master', str(master['id']))))

class MasterEndpoint(base.Endpoint):

    pathPattern = ( 'master', 'i:masterid' )

    def get(self, options, kwargs):
        d = self.master.db.masters.getMaster(kwargs['masterid'])
        @d.addCallback
        def process(m):
            return _db2data(m) if m else None
        return d


class MastersEndpoint(base.Endpoint):

    pathPattern = ( 'master', )
    rootLinkName = 'masters'

    def get(self, options, kwargs):
        d = self.master.db.masters.getMasters()
        @d.addCallback
        def process(masterlist):
            return [ _db2data(m) for m in masterlist ]
        return d

    def startConsuming(self, callback, options, kwargs):
        return self.master.mq.startConsuming(callback,
                ('master', None, None))


class MasterResourceType(base.ResourceType):

    type = "master"
    endpoints = [ MasterEndpoint, MastersEndpoint ]
    keyFields = [ 'masterid' ]

    @base.updateMethod
    @defer.inlineCallbacks
    def masterActive(self, name, masterid, _reactor=reactor):
        activated = yield self.master.db.masters.setMasterState(
                masterid=masterid, active=True, _reactor=_reactor)
        if activated:
            self.produceEvent(
                dict(masterid=masterid, name=name, active=True),
                'started')

        # check for "expired" masters, while we're here.  We're called every
        # minute, but we want to allow a fwe such periods to pass before we
        # assume another master is dead, to account for clock skew and busy
        # masters.
        too_old = epoch2datetime(_reactor.seconds() - 60*EXPIRE_MINUTES)
        masters = yield self.master.db.masters.getMasters()
        for m in masters:
            if m['last_active'] >= too_old:
                continue

            # mark the master inactive, and send a message on its behalf
            deactivated = yield self.master.db.masters.setMasterState(
                    masterid=m['id'], active=False, _reactor=_reactor)
            if deactivated:
                self.produceEvent(
                    dict(masterid=m['id'], name=m['name'],
                        active=False),
                    'stopped')

    @base.updateMethod
    @defer.inlineCallbacks
    def masterStopped(self, name, masterid):
        deactivated = yield self.master.db.masters.setMasterState(
                masterid=masterid, active=False)
        if deactivated:
            self.produceEvent(
                dict(masterid=masterid, name=name, active=False),
                'stopped')
