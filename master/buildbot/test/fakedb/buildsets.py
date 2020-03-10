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

import json

from twisted.internet import defer

from buildbot.db import buildsets
from buildbot.test.fakedb.base import FakeDBComponent
from buildbot.test.fakedb.buildrequests import BuildRequest
from buildbot.test.fakedb.row import Row
from buildbot.util import datetime2epoch
from buildbot.util import epoch2datetime


class Buildset(Row):
    table = "buildsets"

    defaults = dict(
        id=None,
        external_idstring='extid',
        reason='because',
        submitted_at=12345678,
        complete=0,
        complete_at=None,
        results=-1,
        parent_buildid=None,
        parent_relationship=None,
    )

    id_column = 'id'


class BuildsetProperty(Row):
    table = "buildset_properties"

    defaults = dict(
        buildsetid=None,
        property_name='prop',
        property_value='[22, "fakedb"]',
    )

    foreignKeys = ('buildsetid',)
    required_columns = ('buildsetid', )


class BuildsetSourceStamp(Row):
    table = "buildset_sourcestamps"

    defaults = dict(
        id=None,
        buildsetid=None,
        sourcestampid=None,
    )

    foreignKeys = ('buildsetid', 'sourcestampid')
    required_columns = ('buildsetid', 'sourcestampid', )
    id_column = 'id'


class FakeBuildsetsComponent(FakeDBComponent):

    def setUp(self):
        self.buildsets = {}
        self.completed_bsids = set()
        self.buildset_sourcestamps = {}

    def insertTestData(self, rows):
        for row in rows:
            if isinstance(row, Buildset):
                bs = self.buildsets[row.id] = row.values.copy()
                bs['properties'] = {}

        for row in rows:
            if isinstance(row, BuildsetProperty):
                assert row.buildsetid in self.buildsets
                n = row.property_name
                v, src = tuple(json.loads(row.property_value))
                self.buildsets[row.buildsetid]['properties'][n] = (v, src)

        for row in rows:
            if isinstance(row, BuildsetSourceStamp):
                assert row.buildsetid in self.buildsets
                self.buildset_sourcestamps.setdefault(row.buildsetid,
                                                      []).append(row.sourcestampid)

    # component methods

    def _newBsid(self):
        bsid = 200
        while bsid in self.buildsets:
            bsid += 1
        return bsid

    @defer.inlineCallbacks
    def addBuildset(self, sourcestamps, reason, properties, builderids, waited_for,
                    external_idstring=None, submitted_at=None,
                    parent_buildid=None, parent_relationship=None):
        # We've gotten this wrong a couple times.
        assert isinstance(
            waited_for, bool), 'waited_for should be boolean: %r' % waited_for

        # calculate submitted at
        if submitted_at is not None:
            submitted_at = datetime2epoch(submitted_at)
        else:
            submitted_at = int(self.reactor.seconds())

        bsid = self._newBsid()
        br_rows = []
        for builderid in builderids:
            br_rows.append(
                BuildRequest(buildsetid=bsid, builderid=builderid, waited_for=waited_for,
                             submitted_at=submitted_at))

        self.db.buildrequests.insertTestData(br_rows)

        # make up a row and keep its dictionary, with the properties tacked on
        bsrow = Buildset(id=bsid, reason=reason,
                         external_idstring=external_idstring,
                         submitted_at=submitted_at,
                         parent_buildid=parent_buildid, parent_relationship=parent_relationship)

        self.buildsets[bsid] = bsrow.values.copy()
        self.buildsets[bsid]['properties'] = properties

        # add sourcestamps
        ssids = []
        for ss in sourcestamps:
            if not isinstance(ss, type(1)):
                ss = yield self.db.sourcestamps.findSourceStampId(**ss)
            ssids.append(ss)
        self.buildset_sourcestamps[bsid] = ssids

        return (bsid, {br.builderid: br.id for br in br_rows})

    def completeBuildset(self, bsid, results, complete_at=None):
        if bsid not in self.buildsets or self.buildsets[bsid]['complete']:
            raise buildsets.AlreadyCompleteError()

        if complete_at is not None:
            complete_at = datetime2epoch(complete_at)
        else:
            complete_at = int(self.reactor.seconds())

        self.buildsets[bsid]['results'] = results
        self.buildsets[bsid]['complete'] = 1
        self.buildsets[bsid]['complete_at'] = complete_at
        return defer.succeed(None)

    def getBuildset(self, bsid):
        if bsid not in self.buildsets:
            return defer.succeed(None)
        row = self.buildsets[bsid]
        return defer.succeed(self._row2dict(row))

    def getBuildsets(self, complete=None, resultSpec=None):
        rv = []
        for bs in self.buildsets.values():
            if complete is not None:
                if complete and bs['complete']:
                    rv.append(self._row2dict(bs))
                elif not complete and not bs['complete']:
                    rv.append(self._row2dict(bs))
            else:
                rv.append(self._row2dict(bs))
        if resultSpec is not None:
            rv = self.applyResultSpec(rv, resultSpec)
        return defer.succeed(rv)

    @defer.inlineCallbacks
    def getRecentBuildsets(self, count=None, branch=None, repository=None,
                           complete=None):
        if not count:
            return []
        rv = []
        for bs in (yield self.getBuildsets(complete=complete)):
            if branch or repository:
                ok = True
                if not bs['sourcestamps']:
                    # no sourcestamps -> no match
                    ok = False
                for ssid in bs['sourcestamps']:
                    ss = yield self.db.sourcestamps.getSourceStamp(ssid)
                    if branch and ss['branch'] != branch:
                        ok = False
                    if repository and ss['repository'] != repository:
                        ok = False
            else:
                ok = True

            if ok:
                rv.append(bs)

        rv.sort(key=lambda bs: -bs['bsid'])

        return list(reversed(rv[:count]))

    def _row2dict(self, row):
        row = row.copy()
        row['complete_at'] = epoch2datetime(row['complete_at'])
        row['submitted_at'] = epoch2datetime(row['submitted_at'])
        row['complete'] = bool(row['complete'])
        row['bsid'] = row['id']
        row['sourcestamps'] = self.buildset_sourcestamps.get(row['id'], [])
        del row['id']
        del row['properties']
        return row

    def getBuildsetProperties(self, key, no_cache=False):
        if key in self.buildsets:
            return defer.succeed(
                self.buildsets[key]['properties'])
        return defer.succeed({})

    # fake methods

    def fakeBuildsetCompletion(self, bsid, result):
        assert bsid in self.buildsets
        self.buildsets[bsid]['results'] = result
        self.completed_bsids.add(bsid)

    # assertions

    def assertBuildsetCompletion(self, bsid, complete):
        """Assert that the completion state of buildset BSID is COMPLETE"""
        actual = self.buildsets[bsid]['complete']
        self.t.assertTrue(
            (actual and complete) or (not actual and not complete))

    def assertBuildset(self, bsid=None, expected_buildset=None):
        """Assert that the given buildset looks as expected; the ssid parameter
        of the buildset is omitted.  Properties are converted with asList and
        sorted.  Attributes complete, complete_at, submitted_at, results, and parent_*
        are ignored if not specified."""
        self.t.assertIn(bsid, self.buildsets)
        buildset = self.buildsets[bsid].copy()
        del buildset['id']

        # clear out some columns if the caller doesn't care
        columns = [
            'complete', 'complete_at', 'submitted_at', 'results', 'parent_buildid',
            'parent_relationship'
        ]
        for col in columns:
            if col not in expected_buildset:
                del buildset[col]

        if buildset['properties']:
            buildset['properties'] = sorted(buildset['properties'].items())

        self.t.assertEqual(buildset, expected_buildset)
        return bsid
