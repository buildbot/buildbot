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

import datetime
from twisted.trial import unittest
from twisted.internet import defer, task
from buildbot.db import buildsets
from buildbot.util import json, UTC, epoch2datetime, datetime2epoch
from buildbot.test.util import connector_component, interfaces, types
from buildbot.test.fake import fakemaster, fakedb

class Tests(interfaces.InterfaceTests):

    def setUpTests(self):
        self.now = 9272359
        self.clock = task.Clock()
        self.clock.advance(self.now)

        # set up a sourcestamp with id 234 for use below
        return self.insertTestData([
            fakedb.SourceStampSet(id=234),
            fakedb.SourceStamp(id=234, sourcestampsetid=234),
            ])

    def test_signature_addBuildset(self):
        @self.assertArgSpecMatches(self.db.buildsets.addBuildset)
        def addBuildset(self, sourcestampsetid, reason, properties,
                builderNames, external_idstring=None, submitted_at=None):
            pass

    def test_signature_completeBuildset(self):
        @self.assertArgSpecMatches(self.db.buildsets.completeBuildset)
        def completeBuildset(self, bsid, results, complete_at=None):
            pass

    def test_signature_getBuildset(self):
        @self.assertArgSpecMatches(self.db.buildsets.getBuildset)
        def getBuildset(self, bsid):
            pass

    def test_signature_getBuildsets(self):
        @self.assertArgSpecMatches(self.db.buildsets.getBuildsets)
        def getBuildsets(self, complete=None):
            pass

    def test_signature_getRecentBuildsets(self):
        @self.assertArgSpecMatches(self.db.buildsets.getRecentBuildsets)
        def getBuildsets(self, count=None, branch=None, repository=None,
                complete=None):
            pass

    def test_signature_getBuildsetProperties(self):
        @self.assertArgSpecMatches(self.db.buildsets.getBuildsetProperties)
        def getBuildsetProperties(self, bsid):
            pass

    def test_addBuildset_getBuildset(self):
        d = defer.succeed(None)
        d.addCallback(lambda _ :
            self.db.buildsets.addBuildset(sourcestampsetid=234, reason='because',
                properties={}, builderNames=['bldr'], external_idstring='extid',
                _reactor=self.clock))
        # TODO: verify buildrequests too
        d.addCallback(lambda (bsid,brids) :
            self.db.buildsets.getBuildset(bsid))
        @d.addCallback
        def check(bsdict):
            types.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(bsdict, dict(external_idstring='extid',
                reason='because', sourcestampsetid=234,
                submitted_at=datetime.datetime(1970, 4, 18, 7, 39, 19,
                                               tzinfo=UTC),
                complete=False, complete_at=None, results=-1,
                bsid=bsdict['bsid']))
        return d

    def test_addBuildset_getBuildset_explicit_submitted_at(self):
        d = defer.succeed(None)
        d.addCallback(lambda _ :
            self.db.buildsets.addBuildset(sourcestampsetid=234, reason='because',
                properties={}, builderNames=['bldr'], external_idstring='extid',
                submitted_at=epoch2datetime(8888888), _reactor=self.clock))
        d.addCallback(lambda (bsid,brids) :
            self.db.buildsets.getBuildset(bsid))
        @d.addCallback
        def check(bsdict):
            types.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(bsdict, dict(external_idstring='extid',
                reason='because', sourcestampsetid=234,
                submitted_at=datetime.datetime(1970, 4, 13, 21, 8, 8,
                                                tzinfo=UTC),
                complete=False, complete_at=None, results=-1,
                bsid=bsdict['bsid']))
        return d

    def do_test_getBuildsetProperties(self, buildsetid, rows, expected):
        d = self.insertTestData(rows)
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildsetProperties(buildsetid))
        def check(props):
            self.assertEqual(props, expected)
        d.addCallback(check)
        return d

    def test_getBuildsetProperties_multiple(self):
        return self.do_test_getBuildsetProperties(91, [
            fakedb.Buildset(id=91, sourcestampsetid=234, complete=0,
                    results=-1, submitted_at=0),
            fakedb.BuildsetProperty(buildsetid=91, property_name='prop1',
                    property_value='["one", "fake1"]'),
            fakedb.BuildsetProperty(buildsetid=91, property_name='prop2',
                    property_value='["two", "fake2"]'),
        ], dict(prop1=("one", "fake1"), prop2=("two", "fake2")))

    def test_getBuildsetProperties_empty(self):
        return self.do_test_getBuildsetProperties(91, [
            fakedb.Buildset(id=91, sourcestampsetid=234, complete=0,
                    results=-1, submitted_at=0),
        ], dict())

    def test_getBuildsetProperties_nosuch(self):
        "returns an empty dict even if no such buildset exists"
        return self.do_test_getBuildsetProperties(91, [], dict())

    def test_getBuildset_incomplete_None(self):
        d = self.insertTestData([
            fakedb.Buildset(id=91, sourcestampsetid=234, complete=0,
                    complete_at=None, results=-1, submitted_at=266761875,
                    external_idstring='extid', reason='rsn'),
        ])
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildset(91))
        def check(bsdict):
            types.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(bsdict, dict(external_idstring='extid',
                reason='rsn', sourcestampsetid=234,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete=False, complete_at=None, results=-1,
                bsid=91))
        d.addCallback(check)
        return d

    def test_getBuildset_incomplete_zero(self):
        d = self.insertTestData([
            fakedb.Buildset(id=91, sourcestampsetid=234, complete=0,
                    complete_at=0, results=-1, submitted_at=266761875,
                    external_idstring='extid', reason='rsn'),
        ])
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildset(91))
        def check(bsdict):
            types.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(bsdict, dict(external_idstring='extid',
                reason='rsn', sourcestampsetid=234,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete=False, complete_at=None, results=-1,
                bsid=91))
        d.addCallback(check)
        return d

    def test_getBuildset_complete(self):
        d = self.insertTestData([
            fakedb.Buildset(id=91, sourcestampsetid=234, complete=1,
                    complete_at=298297875, results=-1, submitted_at=266761875,
                    external_idstring='extid', reason='rsn'),
        ])
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildset(91))
        def check(bsdict):
            types.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(bsdict, dict(external_idstring='extid',
                reason='rsn', sourcestampsetid=234,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete=True,
                complete_at=datetime.datetime(1979, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                results=-1,
                bsid=91))
        d.addCallback(check)
        return d

    def test_getBuildset_nosuch(self):
        d = self.db.buildsets.getBuildset(91)
        def check(bsdict):
            self.assertEqual(bsdict, None)
        d.addCallback(check)
        return d

    def insert_test_getBuildsets_data(self):
        return self.insertTestData([
            fakedb.Buildset(id=91, sourcestampsetid=234, complete=0,
                    complete_at=298297875, results=-1, submitted_at=266761875,
                    external_idstring='extid', reason='rsn1'),
            fakedb.Buildset(id=92, sourcestampsetid=234, complete=1,
                    complete_at=298297876, results=7, submitted_at=266761876,
                    external_idstring='extid', reason='rsn2'),
        ])

    def test_getBuildsets_empty(self):
        d = self.db.buildsets.getBuildsets()
        def check(bsdictlist):
            self.assertEqual(bsdictlist, [])
        d.addCallback(check)
        return d

    def test_getBuildsets_all(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildsets())
        def check(bsdictlist):
            for bsdict in bsdictlist:
                types.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(sorted(bsdictlist), sorted([
              dict(external_idstring='extid', reason='rsn1', sourcestampsetid=234,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete_at=datetime.datetime(1979, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete=False, results=-1, bsid=91),
              dict(external_idstring='extid', reason='rsn2', sourcestampsetid=234,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 16,
                                               tzinfo=UTC),
                complete_at=datetime.datetime(1979, 6, 15, 12, 31, 16,
                                               tzinfo=UTC),
                complete=True, results=7, bsid=92),
            ]))
        d.addCallback(check)
        return d

    def test_getBuildsets_complete(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildsets(complete=True))
        def check(bsdictlist):
            for bsdict in bsdictlist:
                types.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(bsdictlist, [
              dict(external_idstring='extid', reason='rsn2', sourcestampsetid=234,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 16,
                                               tzinfo=UTC),
                complete_at=datetime.datetime(1979, 6, 15, 12, 31, 16,
                                               tzinfo=UTC),
                complete=True, results=7, bsid=92),
            ])
        d.addCallback(check)
        return d

    def test_getBuildsets_incomplete(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildsets(complete=False))
        def check(bsdictlist):
            for bsdict in bsdictlist:
                types.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(bsdictlist, [
              dict(external_idstring='extid', reason='rsn1', sourcestampsetid=234,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete_at=datetime.datetime(1979, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete=False, results=-1, bsid=91),
            ])
        d.addCallback(check)
        return d

    def test_completeBuildset_already_completed(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.completeBuildset(bsid=92, results=6,
                                                   _reactor=self.clock))
        return self.assertFailure(d, KeyError)

    def test_completeBuildset_missing(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.completeBuildset(bsid=93, results=6,
                                                   _reactor=self.clock))
        return self.assertFailure(d, KeyError)

    def test_completeBuildset(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.completeBuildset(bsid=91, results=6,
                                                   _reactor=self.clock))
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildsets())
        def check(bsdicts):
            bsdicts = [ (bsdict['bsid'], bsdict['complete'],
                         datetime2epoch(bsdict['complete_at']),
                         bsdict['results'])
                        for bsdict in bsdicts ]
            self.assertEqual(sorted(bsdicts), sorted([
                ( 91, 1, self.now, 6),
                ( 92, 1, 298297876, 7) ]))
        d.addCallback(check)
        return d

    def test_completeBuildset_explicit_complete_at(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.completeBuildset(bsid=91, results=6,
                                    complete_at=epoch2datetime(72759)))
        d.addCallback(lambda _ :
                self.db.buildsets.getBuildsets())
        def check(bsdicts):
            bsdicts = [ (bsdict['bsid'], bsdict['complete'],
                         datetime2epoch(bsdict['complete_at']),
                         bsdict['results'])
                        for bsdict in bsdicts ]
            self.assertEqual(sorted(bsdicts), sorted([
                ( 91, 1, 72759, 6),
                ( 92, 1, 298297876, 7) ]))
        d.addCallback(check)
        return d

    def insert_test_getRecentBuildsets_data(self):
        return self.insertTestData([
            fakedb.Change(changeid=91, branch='branch_a', repository='repo_a'),
            fakedb.SourceStamp(id=91, branch='branch_a', repository='repo_a',
                               sourcestampsetid=91),
            fakedb.SourceStampChange(sourcestampid=91, changeid=91),
            fakedb.SourceStampSet(id=91),

            fakedb.Buildset(id=91, sourcestampsetid=91, complete=0,
                    complete_at=298297875, results=-1, submitted_at=266761875,
                    external_idstring='extid', reason='rsn1'),
            fakedb.Buildset(id=92, sourcestampsetid=91, complete=1,
                    complete_at=298297876, results=7, submitted_at=266761876,
                    external_idstring='extid', reason='rsn2'),

            # buildset unrelated to the change
            fakedb.SourceStampSet(id=1),
            fakedb.Buildset(id=93, sourcestampsetid=1, complete=1,
                    complete_at=298297877, results=7, submitted_at=266761877,
                    external_idstring='extid', reason='rsn2'),
        ])

    def test_getRecentBuildsets_all(self):
        d = self.insert_test_getRecentBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.getRecentBuildsets(2, branch='branch_a',
                                                     repository='repo_a'))
        def check(bsdictlist):
            self.assertEqual(bsdictlist, [
              dict(external_idstring='extid', reason='rsn1', sourcestampsetid=91,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete_at=datetime.datetime(1979, 6, 15, 12, 31, 15,
                                               tzinfo=UTC),
                complete=False, results=-1, bsid=91),
              dict(external_idstring='extid', reason='rsn2', sourcestampsetid=91,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 16,
                                               tzinfo=UTC),
                complete_at=datetime.datetime(1979, 6, 15, 12, 31, 16,
                                               tzinfo=UTC),
                complete=True, results=7, bsid=92),
            ])
        d.addCallback(check)
        return d

    def test_getRecentBuildsets_one(self):
        d = self.insert_test_getRecentBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.getRecentBuildsets(1, branch='branch_a',
                                                     repository='repo_a'))
        def check(bsdictlist):
            self.assertEqual(bsdictlist, [
              dict(external_idstring='extid', reason='rsn2', sourcestampsetid=91,
                submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 16,
                                               tzinfo=UTC),
                complete_at=datetime.datetime(1979, 6, 15, 12, 31, 16,
                                               tzinfo=UTC),
                complete=True, results=7, bsid=92),
            ])
        d.addCallback(check)
        return d

    def test_getRecentBuildsets_zero(self):
        d = self.insert_test_getRecentBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.getRecentBuildsets(0, branch='branch_a',
                                                     repository='repo_a'))
        def check(bsdictlist):
            self.assertEqual(bsdictlist, [])
        d.addCallback(check)
        return d

    def test_getRecentBuildsets_noBranchMatch(self):
        d = self.insert_test_getRecentBuildsets_data()
        d.addCallback(lambda _ :
                self.db.buildsets.getRecentBuildsets(2, branch='bad_branch',
                                                     repository='repo_a'))
        def check(bsdictlist):
            self.assertEqual(bsdictlist, [])
        d.addCallback(check)
        return d

    def test_getRecentBuildsets_noRepoMatch(self):
          d = self.insert_test_getRecentBuildsets_data()
          d.addCallback(lambda _ :
                  self.db.buildsets.getRecentBuildsets(2, branch='branch_a',
                                                       repository='bad_repo'))
          def check(bsdictlist):
              self.assertEqual(bsdictlist, [])
          d.addCallback(check)
          return d


class RealTests(Tests):

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # tests

    def test_addBuildset_simple(self):
        d = defer.succeed(None)
        d.addCallback(lambda _ :
            self.db.buildsets.addBuildset(sourcestampsetid=234, reason='because',
                properties={}, builderNames=['bldr'], external_idstring='extid',
                _reactor=self.clock))
        def check((bsid, brids)):
            def thd(conn):
                # we should only have one brid
                self.assertEqual(len(brids), 1)

                # should see one buildset row
                r = conn.execute(self.db.model.buildsets.select())
                rows = [ (row.id, row.external_idstring, row.reason,
                          row.sourcestampsetid, row.complete, row.complete_at,
                          row.submitted_at, row.results) for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( bsid, 'extid', 'because', 234, 0, None, self.now, -1) ])

                # and one buildrequests row
                r = conn.execute(self.db.model.buildrequests.select())

                rows = [ (row.buildsetid, row.id, row.buildername,
                    row.priority, row.complete, row.results,
                    row.submitted_at, row.complete_at)
                          for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( bsid, brids['bldr'], 'bldr', 0, 0,
                        -1, self.now, None) ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_addBuildset_bigger(self):
        props = dict(prop=(['list'], 'test'))
        d = defer.succeed(None)
        d.addCallback(lambda _ :
            self.db.buildsets.addBuildset(sourcestampsetid=234, reason='because',
                                properties=props, builderNames=['a', 'b']))
        def check((bsid, brids)):
            def thd(conn):
                self.assertEqual(len(brids), 2)

                # should see one buildset row
                r = conn.execute(self.db.model.buildsets.select())
                rows = [ (row.id, row.external_idstring, row.reason,
                          row.sourcestampsetid, row.complete,
                          row.complete_at, row.results)
                          for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( bsid, None, u'because', 234, 0, None, -1) ])

                # one property row
                r = conn.execute(self.db.model.buildset_properties.select())
                rows = [ (row.buildsetid, row.property_name, row.property_value)
                          for row in r.fetchall() ]
                self.assertEqual(rows,
                    [ ( bsid, 'prop', json.dumps([ ['list'], 'test' ]) ) ])

                # and two buildrequests rows (and don't re-check the default columns)
                r = conn.execute(self.db.model.buildrequests.select())
                rows = [ (row.buildsetid, row.id, row.buildername)
                          for row in r.fetchall() ]

                # we don't know which of the brids is assigned to which
                # buildername, but either one will do
                self.assertEqual(sorted(rows),
                    [ ( bsid, brids['a'], 'a'), (bsid, brids['b'], 'b') ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master(wantDb=True, testcase=self)
        self.db = self.master.db
        self.insertTestData = self.db.insertTestData
        return self.setUpTests()


class TestRealDB(unittest.TestCase,
        connector_component.ConnectorComponentMixin,
        RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=[ 'patches', 'changes', 'sourcestamp_changes',
                'buildsets', 'buildset_properties', 'objects',
                'buildrequests', 'sourcestamps', 'sourcestampsets' ])

        @d.addCallback
        def finish_setup(_):
            self.db.buildsets = buildsets.BuildsetsConnectorComponent(self.db)
        d.addCallback(lambda _ : self.setUpTests())
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()
