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
from buildbot.util import datetime2epoch

def _db2data(master):
    return dict(masterid=master['id'],
                master_name=master['master_name'],
                active=master['active'],
                last_checkin=datetime2epoch(master['last_checkin']),
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
    def checkinMaster(self, master_name, masterid, _reactor=reactor):
        activated = yield self.master.db.masters.setMasterState(
                masterid=masterid, active=True, _reactor=_reactor)
        if activated:
            self.produceEvent(
                dict(masterid=masterid, master_name=master_name, active=True),
                'started')

    @base.updateMethod
    @defer.inlineCallbacks
    def checkoutMaster(self, master_name, masterid):
        deactivated = yield self.master.db.masters.setMasterState(
                masterid=masterid, active=False)
        if deactivated:
            self.produceEvent(
                dict(masterid=masterid, master_name=master_name, active=False),
                'stopped')
