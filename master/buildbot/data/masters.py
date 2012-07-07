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

class MasterEndpoint(base.Endpoint):

    pathPattern = ( 'master', 'i:masterid' )

    def get(self, options, kwargs):
        if kwargs['masterid'] != 1:
            return defer.succeed(None)
        return defer.succeed(
            dict(masterid=1,
                 name=unicode(self.master.master_name),
                 state=u'started',
                 link=base.Link(('master', str(kwargs['masterid'])))))


class MastersEndpoint(base.Endpoint):

    pathPattern = ( 'master', )
    rootLinkName = 'masters'

    def get(self, options, kwargs):
        # TODO: options['count']
        return defer.succeed([
            dict(masterid=1,
                 name=unicode(self.master.master_name),
                 state=u'started',
                 link=base.Link(('master', str(1))))
            ])


class MasterResourceType(base.ResourceType):

    type = "master"
    endpoints = [ MasterEndpoint, MastersEndpoint ]
    keyFields = [ 'masterid' ]

    @base.updateMethod
    @defer.inlineCallbacks
    def setMasterState(self, state=None):
        assert state in ('started', 'stopped')
        # get the masterid and name
        name = unicode(self.master.master_name)
        masterid = yield self.master.getObjectId()
        # and produce the event
        self.produceEvent(
                dict(masterid=masterid, name=name, state=unicode(state)),
                str(state))
