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
from buildbot.util import datetime2epoch

class Db2DataMixin(object):

    def db2data(self, dbdict):
        data = {
            'buildid': dbdict['id'],
            'number': dbdict['number'],
            'builderid': dbdict['builderid'],
            'builder_link': base.Link(('builder', str(dbdict['builderid']))),
            'buildrequestid': dbdict['buildrequestid'],
            'buildrequest_link': base.Link(('buildrequest',
                                           str(dbdict['buildrequestid']))),
            'slaveid': dbdict['slaveid'],
            'slave_link': base.Link(('slave', str(dbdict['slaveid']))),
            'masterid': dbdict['masterid'],
            'master_link': base.Link(('master', str(dbdict['masterid']))),
            'started_at': datetime2epoch(dbdict['started_at']),
            'complete_at': datetime2epoch(dbdict['complete_at']),
            'complete': dbdict['complete_at'] is not None,
            'state_strings': dbdict['state_strings'],
            'results': dbdict['results'],
            'link': base.Link(('build', str(dbdict['id']))),
        }
        return defer.succeed(data)


class BuildEndpoint(Db2DataMixin, base.Endpoint):

    pathPatterns = [
        ( 'build', 'i:buildid' ),
        ( 'builder', 'i:builderid', 'build', 'i:buildid' ),
        ( 'builder', 'i:builderid', 'build', 'number' 'i:number' ),
    ]

    @defer.inlineCallbacks
    def get(self, options, kwargs):
        if 'buildid' in kwargs:
            dbdict = yield self.master.db.builds.getBuild(kwargs['buildid'])
        else:
            bldr = kwargs['builderid']
            num = kwargs['number']
            dbdict = yield self.master.db.builds.getBuildByNumber(bldr, num)
        if 'builderid' in kwargs:
            if not dbdict or dbdict['builderid'] != kwargs['builderid']:
                return
        yield defer.returnValue((yield self.db2data(dbdict))
                                if dbdict else None)


class BuildsEndpoint(Db2DataMixin, base.Endpoint):

    pathPatterns = [
        ( 'build', ),
        ( 'builder', 'i:builderid', 'build', ),
        ( 'buildrequest', 'i:buildrequestid', 'build', ),
    ]
    rootLinkName = 'builds'

    @defer.inlineCallbacks
    def get(self, options, kwargs):
        builds = yield self.master.db.builds.getBuilds(
                                builderid=kwargs.get('builderid'),
                                buildrequestid=kwargs.get('buildrequestid'))
        yield defer.returnValue(
                [ (yield self.db2data(schdict)) for schdict in builds ])

    def startConsuming(self, callback, options, kwargs):
        return self.master.mq.startConsuming(callback,
                ('build', None, None, None))


class BuildsResourceType(base.ResourceType):

    type = "build"
    endpoints = [ BuildEndpoint, BuildsEndpoint ]
    keyFields = [ 'builderid', 'buildid' ]

    @base.updateMethod
    def newBuild(self, builderid, buildrequestid, slaveid):
        return self.master.db.builds.addBuild(
                builderid=builderid,
                buildrequestid=buildrequestid,
                slaveid=slaveid,
                masterid=self.master.masterid,
                state_strings=[u'starting'])

    @base.updateMethod
    def setBuildStateStrings(self, buildid, state_strings):
        return self.master.db.builds.setBuildStateStrings(
                buildid=buildid, state_strings=state_strings)

    @base.updateMethod
    def finishBuild(self, buildid, results):
        return self.master.db.builds.finishBuild(
                buildid=buildid, results=results)
