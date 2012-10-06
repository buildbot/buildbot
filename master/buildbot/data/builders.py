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

class BuilderEndpoint(base.Endpoint):

    pathPatterns = [ ( 'builder', 'i:builderid' ),
                     ( 'master', 'i:masterid', 'builder', 'i:builderid' ) ]

    def get(self, options, kwargs):
        rtype = self.master.data.rtypes['builder']
        builderid = kwargs['builderid']
        if builderid not in rtype.builderIds:
            return defer.succeed(None)
        return defer.succeed(
            dict(builderid=builderid,
                 name=rtype.builderIds[builderid],
                 link=base.Link(('builder', str(kwargs['builderid'])))))


class BuildersEndpoint(base.Endpoint):

    rootLinkName = 'builders'
    pathPatterns = [ ( 'builder', ),
                     ( 'master', 'i:masterid', 'builder' ) ]

    def get(self, options, kwargs):
        rtype = self.master.data.rtypes['builder']
        names = set(rtype.builders)
        with_ids = [ (id, name) for id, name in rtype.builderIds.iteritems()
                     if name in names ]
        with_ids.sort()
        return defer.succeed([
            dict(builderid=id,
                 name=name,
                 link=base.Link(('builder', str(id))))
            for id, name in with_ids ])

    def startConsuming(self, callback, options, kwargs):
        return self.master.mq.startConsuming(callback,
                ('builder', None, 'new'))


class BuildersResourceType(base.ResourceType):

    type = "builder"
    endpoints = [
        BuilderEndpoint, BuildersEndpoint,
    ]
    keyFields = [ 'builderid' ]

    def __init__(self, master):
        base.ResourceType.__init__(self, master)
        self.builderIds = {} # name : id
        self.builders = [] # list of names
        self.masterid = None

    @base.updateMethod
    @defer.inlineCallbacks
    def updateBuilderList(self, masterid, builderNames):
        self.masterid = masterid
        for name in builderNames:
            if name not in self.builderIds:
                builderid = len(self.builderIds)+1
                self.builderIds[builderid] = name
                self.produceEvent(
                        dict(builderid=builderid, name=name),
                        'new')
        self.builders = builderNames
        yield defer.returnValue(None)
