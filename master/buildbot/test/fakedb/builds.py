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

from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.row import Row
from buildbot.test.util import validation
from buildbot.util import epoch2datetime


class Build(Row):
    table = "builds"

    defaults = dict(
        id=None,
        number=29,
        buildrequestid=None,
        builderid=None,
        workerid=-1,
        masterid=None,
        started_at=1304262222,
        complete_at=None,
        state_string="test",
        results=None)

    id_column = 'id'
    foreignKeys = ('buildrequestid', 'masterid', 'workerid', 'builderid')
    required_columns = ('buildrequestid', 'masterid', 'workerid')


class BuildProperty(Row):
    table = "build_properties"
    defaults = dict(
        buildid=None,
        name='prop',
        value=42,
        source='fakedb'
    )

    foreignKeys = ('buildid',)
    required_columns = ('buildid',)


class FakeBuildsComponent(FakeDBComponent):

    def setUp(self):
        self.builds = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Build):
                build = self.builds[row.id] = row.values.copy()
                build['properties'] = {}

        for row in rows:
            if isinstance(row, BuildProperty):
                assert row.buildid in self.builds
                self.builds[row.buildid]['properties'][
                    row.name] = (row.value, row.source)

    # component methods

    def _newId(self):
        id = 100
        while id in self.builds:
            id += 1
        return id

    def _row2dict(self, row):
        return dict(
            id=row['id'],
            number=row['number'],
            buildrequestid=row['buildrequestid'],
            builderid=row['builderid'],
            masterid=row['masterid'],
            workerid=row['workerid'],
            started_at=epoch2datetime(row['started_at']),
            complete_at=epoch2datetime(row['complete_at']),
            state_string=row['state_string'],
            results=row['results'])

    def getBuild(self, buildid):
        row = self.builds.get(buildid)
        if not row:
            return defer.succeed(None)

        return defer.succeed(self._row2dict(row))

    def getBuildByNumber(self, builderid, number):
        for row in self.builds.values():
            if row['builderid'] == builderid and row['number'] == number:
                return defer.succeed(self._row2dict(row))
        return defer.succeed(None)

    def getBuilds(self, builderid=None, buildrequestid=None, workerid=None, complete=None,
                  resultSpec=None):
        ret = []
        for (id, row) in self.builds.items():
            if builderid is not None and row['builderid'] != builderid:
                continue
            if buildrequestid is not None and row['buildrequestid'] != buildrequestid:
                continue
            if workerid is not None and row['workerid'] != workerid:
                continue
            if complete is not None and complete != (row['complete_at'] is not None):
                continue
            ret.append(self._row2dict(row))
        if resultSpec is not None:
            ret = self.applyResultSpec(ret, resultSpec)
        return defer.succeed(ret)

    def addBuild(self, builderid, buildrequestid, workerid, masterid,
                 state_string):
        validation.verifyType(self.t, 'state_string', state_string,
                              validation.StringValidator())
        id = self._newId()
        number = max([0] + [r['number'] for r in self.builds.values()
                            if r['builderid'] == builderid]) + 1
        self.builds[id] = dict(id=id, number=number,
                               buildrequestid=buildrequestid, builderid=builderid,
                               workerid=workerid, masterid=masterid,
                               state_string=state_string,
                               started_at=self.reactor.seconds(),
                               complete_at=None,
                               results=None)
        return defer.succeed((id, number))

    def setBuildStateString(self, buildid, state_string):
        validation.verifyType(self.t, 'state_string', state_string,
                              validation.StringValidator())
        b = self.builds.get(buildid)
        if b:
            b['state_string'] = state_string
        return defer.succeed(None)

    def finishBuild(self, buildid, results):
        now = self.reactor.seconds()
        b = self.builds.get(buildid)
        if b:
            b['complete_at'] = now
            b['results'] = results
        return defer.succeed(None)

    def getBuildProperties(self, bid):
        if bid in self.builds:
            return defer.succeed(self.builds[bid]['properties'])
        return defer.succeed({})

    def setBuildProperty(self, bid, name, value, source):
        assert bid in self.builds
        self.builds[bid]['properties'][name] = (value, source)
        return defer.succeed(None)

    @defer.inlineCallbacks
    def getBuildsForChange(self, changeid):
        change = yield self.db.changes.getChange(changeid)
        bsets = yield self.db.buildsets.getBuildsets()
        breqs = yield self.db.buildrequests.getBuildRequests()
        builds = yield self.db.builds.getBuilds()

        results = []
        for bset in bsets:
            for ssid in bset['sourcestamps']:
                if change['sourcestampid'] == ssid:
                    bset['changeid'] = changeid
                    results.append({'buildsetid': bset['bsid']})

        for breq in breqs:
            for result in results:
                if result['buildsetid'] == breq['buildsetid']:
                    result['buildrequestid'] = breq['buildrequestid']

        for build in builds:
            for result in results:
                if result['buildrequestid'] == build['buildrequestid']:
                    result['id'] = build['id']
                    result['number'] = build['number']
                    result['builderid'] = build['builderid']
                    result['workerid'] = build['workerid']
                    result['masterid'] = build['masterid']
                    result['started_at'] = epoch2datetime(1304262222)
                    result['complete_at'] = build['complete_at']
                    result['state_string'] = build['state_string']
                    result['results'] = build['results']

        for result in results:
            del result['buildsetid']

        return results
