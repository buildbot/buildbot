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

import datetime
import json

import mock

from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest

from buildbot.db import buildsets
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import db
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from buildbot.util import UTC
from buildbot.util import datetime2epoch
from buildbot.util import epoch2datetime


class Tests(interfaces.InterfaceTests):

    def setUpTests(self):
        self.now = 9272359
        self.clock = task.Clock()
        self.clock.advance(self.now)

        # set up a sourcestamp with id 234 for use below
        return self.insertTestData([
            fakedb.SourceStamp(id=234),
            fakedb.Builder(id=1, name='bldr1'),
            fakedb.Builder(id=2, name='bldr2'),
        ])

    def test_signature_addBuildset(self):
        @self.assertArgSpecMatches(self.db.buildsets.addBuildset)
        def addBuildset(self, sourcestamps, reason, properties,
                        builderids, waited_for, external_idstring=None, submitted_at=None,
                        parent_buildid=None, parent_relationship=None):
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
        def getBuildsets(self, complete=None, resultSpec=None):
            pass

    def test_signature_getRecentBuildsets(self):
        @self.assertArgSpecMatches(self.db.buildsets.getRecentBuildsets)
        def getBuildsets(self, count=None, branch=None, repository=None,
                         complete=None):
            pass

    def test_signature_getBuildsetProperties(self):
        @self.assertArgSpecMatches(self.db.buildsets.getBuildsetProperties)
        def getBuildsetProperties(self, key, no_cache=False):
            pass

    @defer.inlineCallbacks
    def test_addBuildset_getBuildset(self):
        bsid, brids = yield self.db.buildsets.addBuildset(sourcestamps=[234],
                                                          reason='because', properties={}, builderids=[1],
                                                          external_idstring='extid', _reactor=self.clock, waited_for=False)
        # TODO: verify buildrequests too
        bsdict = yield self.db.buildsets.getBuildset(bsid)
        validation.verifyDbDict(self, 'bsdict', bsdict)
        self.assertEqual(bsdict, dict(external_idstring='extid',
                                      reason='because', sourcestamps=[234],
                                      submitted_at=datetime.datetime(1970, 4, 18, 7, 39, 19,
                                                                     tzinfo=UTC),
                                      complete=False, complete_at=None, results=-1,
                                      parent_buildid=None, parent_relationship=None,
                                      bsid=bsid))

    def test_addBuildset_getBuildset_explicit_submitted_at(self):
        d = defer.succeed(None)
        d.addCallback(lambda _:
                      self.db.buildsets.addBuildset(sourcestamps=[234], reason='because',
                                                    properties={}, builderids=[1], external_idstring='extid',
                                                    submitted_at=epoch2datetime(8888888), _reactor=self.clock, waited_for=False))
        d.addCallback(lambda bsid_brids:
                      self.db.buildsets.getBuildset(bsid_brids[0]))

        @d.addCallback
        def check(bsdict):
            validation.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(bsdict, dict(external_idstring='extid',
                                          reason='because', sourcestamps=[234],
                                          submitted_at=datetime.datetime(1970, 4, 13, 21, 8, 8,
                                                                         tzinfo=UTC),
                                          complete=False, complete_at=None, results=-1,
                                          parent_buildid=None, parent_relationship=None,
                                          bsid=bsdict['bsid']))
        return d

    def do_test_getBuildsetProperties(self, buildsetid, rows, expected):
        d = self.insertTestData(rows)
        d.addCallback(lambda _:
                      self.db.buildsets.getBuildsetProperties(buildsetid))

        def check(props):
            self.assertEqual(props, expected)
        d.addCallback(check)
        return d

    def test_getBuildsetProperties_multiple(self):
        return self.do_test_getBuildsetProperties(91, [
            fakedb.Buildset(id=91, complete=0, results=-1, submitted_at=0),
            fakedb.BuildsetProperty(buildsetid=91, property_name='prop1',
                                    property_value='["one", "fake1"]'),
            fakedb.BuildsetProperty(buildsetid=91, property_name='prop2',
                                    property_value='["two", "fake2"]'),
        ], dict(prop1=("one", "fake1"), prop2=("two", "fake2")))

    def test_getBuildsetProperties_empty(self):
        return self.do_test_getBuildsetProperties(91, [
            fakedb.Buildset(id=91, complete=0, results=-1, submitted_at=0),
        ], dict())

    def test_getBuildsetProperties_nosuch(self):
        "returns an empty dict even if no such buildset exists"
        return self.do_test_getBuildsetProperties(91, [], dict())

    def test_getBuildset_incomplete_None(self):
        d = self.insertTestData([
            fakedb.Buildset(id=91, complete=0,
                            complete_at=None, results=-1, submitted_at=266761875,
                            external_idstring='extid', reason='rsn'),
            fakedb.BuildsetSourceStamp(buildsetid=91, sourcestampid=234),
        ])
        d.addCallback(lambda _:
                      self.db.buildsets.getBuildset(91))

        def check(bsdict):
            validation.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(bsdict, dict(external_idstring='extid',
                                          reason='rsn', sourcestamps=[234],
                                          submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                                                         tzinfo=UTC),
                                          complete=False, complete_at=None, results=-1,
                                          bsid=91,
                                          parent_buildid=None, parent_relationship=None))
        d.addCallback(check)
        return d

    def test_getBuildset_incomplete_zero(self):
        d = self.insertTestData([
            fakedb.Buildset(id=91, complete=0,
                            complete_at=0, results=-1, submitted_at=266761875,
                            external_idstring='extid', reason='rsn'),
            fakedb.BuildsetSourceStamp(buildsetid=91, sourcestampid=234),
        ])
        d.addCallback(lambda _:
                      self.db.buildsets.getBuildset(91))

        def check(bsdict):
            validation.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(bsdict, dict(external_idstring='extid',
                                          reason='rsn', sourcestamps=[234],
                                          submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                                                         tzinfo=UTC),
                                          complete=False, complete_at=None, results=-1,
                                          bsid=91,
                                          parent_buildid=None, parent_relationship=None))
        d.addCallback(check)
        return d

    def test_getBuildset_complete(self):
        d = self.insertTestData([
            fakedb.Buildset(id=91, complete=1,
                            complete_at=298297875, results=-1, submitted_at=266761875,
                            external_idstring='extid', reason='rsn'),
            fakedb.BuildsetSourceStamp(buildsetid=91, sourcestampid=234),
        ])
        d.addCallback(lambda _:
                      self.db.buildsets.getBuildset(91))

        def check(bsdict):
            validation.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(bsdict, dict(external_idstring='extid',
                                          reason='rsn', sourcestamps=[234],
                                          submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                                                         tzinfo=UTC),
                                          complete=True,
                                          complete_at=datetime.datetime(1979, 6, 15, 12, 31, 15,
                                                                        tzinfo=UTC),
                                          results=-1,
                                          bsid=91,
                                          parent_buildid=None, parent_relationship=None))
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
            fakedb.Buildset(id=91, complete=0,
                            complete_at=298297875, results=-1, submitted_at=266761875,
                            external_idstring='extid', reason='rsn1'),
            fakedb.BuildsetSourceStamp(buildsetid=91, sourcestampid=234),
            fakedb.Buildset(id=92, complete=1,
                            complete_at=298297876, results=7, submitted_at=266761876,
                            external_idstring='extid', reason='rsn2'),
            fakedb.BuildsetSourceStamp(buildsetid=92, sourcestampid=234),
        ])

    def test_getBuildsets_empty(self):
        d = self.db.buildsets.getBuildsets()

        def check(bsdictlist):
            self.assertEqual(bsdictlist, [])
        d.addCallback(check)
        return d

    def test_getBuildsets_all(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _:
                      self.db.buildsets.getBuildsets())

        def check(bsdictlist):
            def bsdictKey(bsdict):
                return bsdict['reason']

            for bsdict in bsdictlist:
                validation.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(sorted(bsdictlist, key=bsdictKey), sorted([
                dict(external_idstring='extid', reason='rsn1', sourcestamps=[234],
                     submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                                    tzinfo=UTC),
                     complete_at=datetime.datetime(1979, 6, 15, 12, 31, 15,
                                                   tzinfo=UTC),
                     complete=False, results=-1, bsid=91,
                     parent_buildid=None, parent_relationship=None),
                dict(external_idstring='extid', reason='rsn2', sourcestamps=[234],
                     submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 16,
                                                    tzinfo=UTC),
                     complete_at=datetime.datetime(1979, 6, 15, 12, 31, 16,
                                                   tzinfo=UTC),
                     complete=True, results=7, bsid=92,
                     parent_buildid=None, parent_relationship=None),
            ], key=bsdictKey))
        d.addCallback(check)
        return d

    def test_getBuildsets_complete(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _:
                      self.db.buildsets.getBuildsets(complete=True))

        def check(bsdictlist):
            for bsdict in bsdictlist:
                validation.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(bsdictlist, [
                dict(external_idstring='extid', reason='rsn2', sourcestamps=[234],
                     submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 16,
                                                    tzinfo=UTC),
                     complete_at=datetime.datetime(1979, 6, 15, 12, 31, 16,
                                                   tzinfo=UTC),
                     complete=True, results=7, bsid=92,
                     parent_buildid=None, parent_relationship=None),
            ])
        d.addCallback(check)
        return d

    def test_getBuildsets_incomplete(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _:
                      self.db.buildsets.getBuildsets(complete=False))

        def check(bsdictlist):
            for bsdict in bsdictlist:
                validation.verifyDbDict(self, 'bsdict', bsdict)
            self.assertEqual(bsdictlist, [
                dict(external_idstring='extid', reason='rsn1', sourcestamps=[234],
                     submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                                    tzinfo=UTC),
                     complete_at=datetime.datetime(1979, 6, 15, 12, 31, 15,
                                                   tzinfo=UTC),
                     complete=False, results=-1, bsid=91,
                     parent_buildid=None, parent_relationship=None),
            ])
        d.addCallback(check)
        return d

    def test_completeBuildset_already_completed(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _:
                      self.db.buildsets.completeBuildset(bsid=92, results=6,
                                                         _reactor=self.clock))
        return self.assertFailure(d, KeyError)

    def test_completeBuildset_missing(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _:
                      self.db.buildsets.completeBuildset(bsid=93, results=6,
                                                         _reactor=self.clock))
        return self.assertFailure(d, KeyError)

    def test_completeBuildset(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _:
                      self.db.buildsets.completeBuildset(bsid=91, results=6,
                                                         _reactor=self.clock))
        d.addCallback(lambda _:
                      self.db.buildsets.getBuildsets())

        def check(bsdicts):
            bsdicts = [(bsdict['bsid'], bsdict['complete'],
                        datetime2epoch(bsdict['complete_at']),
                        bsdict['results'])
                       for bsdict in bsdicts]
            self.assertEqual(sorted(bsdicts), sorted([
                (91, 1, self.now, 6),
                (92, 1, 298297876, 7)]))
        d.addCallback(check)
        return d

    def test_completeBuildset_explicit_complete_at(self):
        d = self.insert_test_getBuildsets_data()
        d.addCallback(lambda _:
                      self.db.buildsets.completeBuildset(bsid=91, results=6,
                                                         complete_at=epoch2datetime(72759)))
        d.addCallback(lambda _:
                      self.db.buildsets.getBuildsets())

        def check(bsdicts):
            bsdicts = [(bsdict['bsid'], bsdict['complete'],
                        datetime2epoch(bsdict['complete_at']),
                        bsdict['results'])
                       for bsdict in bsdicts]
            self.assertEqual(sorted(bsdicts), sorted([
                (91, 1, 72759, 6),
                (92, 1, 298297876, 7)]))
        d.addCallback(check)
        return d

    def insert_test_getRecentBuildsets_data(self):
        return self.insertTestData([
            fakedb.SourceStamp(id=91, branch='branch_a', repository='repo_a'),

            fakedb.Buildset(id=91, complete=0,
                            complete_at=298297875, results=-1, submitted_at=266761875,
                            external_idstring='extid', reason='rsn1'),
            fakedb.BuildsetSourceStamp(buildsetid=91, sourcestampid=91),
            fakedb.Buildset(id=92, complete=1,
                            complete_at=298297876, results=7, submitted_at=266761876,
                            external_idstring='extid', reason='rsn2'),
            fakedb.BuildsetSourceStamp(buildsetid=92, sourcestampid=91),

            # buildset unrelated to the change
            fakedb.Buildset(id=93, complete=1,
                            complete_at=298297877, results=7, submitted_at=266761877,
                            external_idstring='extid', reason='rsn2'),
        ])

    def test_getRecentBuildsets_all(self):
        d = self.insert_test_getRecentBuildsets_data()
        d.addCallback(lambda _:
                      self.db.buildsets.getRecentBuildsets(2, branch='branch_a',
                                                           repository='repo_a'))

        def check(bsdictlist):
            self.assertEqual(bsdictlist, [
                dict(external_idstring='extid', reason='rsn1', sourcestamps=[91],
                     submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 15,
                                                    tzinfo=UTC),
                     complete_at=datetime.datetime(1979, 6, 15, 12, 31, 15,
                                                   tzinfo=UTC),
                     complete=False, results=-1, bsid=91,
                     parent_buildid=None, parent_relationship=None),
                dict(external_idstring='extid', reason='rsn2', sourcestamps=[91],
                     submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 16,
                                                    tzinfo=UTC),
                     complete_at=datetime.datetime(1979, 6, 15, 12, 31, 16,
                                                   tzinfo=UTC),
                     complete=True, results=7, bsid=92,
                     parent_buildid=None, parent_relationship=None)
            ])
        d.addCallback(check)
        return d

    def test_getRecentBuildsets_one(self):
        d = self.insert_test_getRecentBuildsets_data()
        d.addCallback(lambda _:
                      self.db.buildsets.getRecentBuildsets(1, branch='branch_a',
                                                           repository='repo_a'))

        def check(bsdictlist):
            self.assertEqual(bsdictlist, [
                dict(external_idstring='extid', reason='rsn2', sourcestamps=[91],
                     submitted_at=datetime.datetime(1978, 6, 15, 12, 31, 16,
                                                    tzinfo=UTC),
                     complete_at=datetime.datetime(1979, 6, 15, 12, 31, 16,
                                                   tzinfo=UTC),
                     complete=True, results=7, bsid=92,
                     parent_buildid=None, parent_relationship=None),
            ])
        d.addCallback(check)
        return d

    def test_getRecentBuildsets_zero(self):
        d = self.insert_test_getRecentBuildsets_data()
        d.addCallback(lambda _:
                      self.db.buildsets.getRecentBuildsets(0, branch='branch_a',
                                                           repository='repo_a'))

        def check(bsdictlist):
            self.assertEqual(bsdictlist, [])
        d.addCallback(check)
        return d

    def test_getRecentBuildsets_noBranchMatch(self):
        d = self.insert_test_getRecentBuildsets_data()
        d.addCallback(lambda _:
                      self.db.buildsets.getRecentBuildsets(2, branch='bad_branch',
                                                           repository='repo_a'))

        def check(bsdictlist):
            self.assertEqual(bsdictlist, [])
        d.addCallback(check)
        return d

    def test_getRecentBuildsets_noRepoMatch(self):
        d = self.insert_test_getRecentBuildsets_data()
        d.addCallback(lambda _:
                      self.db.buildsets.getRecentBuildsets(2, branch='branch_a',
                                                           repository='bad_repo'))

        def check(bsdictlist):
            self.assertEqual(bsdictlist, [])
        d.addCallback(check)
        return d


class RealTests(Tests):

    def test_addBuildset_simple(self):
        d = defer.succeed(None)
        d.addCallback(lambda _:
                      self.db.buildsets.addBuildset(sourcestamps=[234], reason='because',
                                                    properties={}, builderids=[2], external_idstring='extid',
                                                    waited_for=True, _reactor=self.clock))

        def check(xxx_todo_changeme):
            (bsid, brids) = xxx_todo_changeme

            def thd(conn):
                # we should only have one brid
                self.assertEqual(len(brids), 1)

                # should see one buildset row
                r = conn.execute(self.db.model.buildsets.select())
                rows = [(row.id, row.external_idstring, row.reason,
                         row.complete, row.complete_at,
                         row.submitted_at, row.results) for row in r.fetchall()]
                self.assertEqual(rows,
                                 [(bsid, 'extid', 'because', 0, None, self.now, -1)])

                # one buildrequests row
                r = conn.execute(self.db.model.buildrequests.select())
                self.assertEqual(r.keys(),
                                 [u'id', u'buildsetid', u'builderid', u'priority',
                                  u'complete', u'results', u'submitted_at',
                                  u'complete_at', u'waited_for'])
                self.assertEqual(r.fetchall(),
                                 [(bsid, brids[2], 2, 0, 0,
                                   -1, self.now, None, 1)])

                # one buildset_sourcestamps row
                r = conn.execute(self.db.model.buildset_sourcestamps.select())
                self.assertEqual(
                    list(r.keys()), [u'id', u'buildsetid', u'sourcestampid'])
                self.assertEqual(r.fetchall(), [(1, bsid, 234)])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_addBuildset_bigger(self):
        props = dict(prop=(['list'], 'test'))
        d = defer.succeed(None)
        d.addCallback(lambda _:
                      self.db.buildsets.addBuildset(sourcestamps=[234], reason='because',
                                                    waited_for=False, properties=props, builderids=[1, 2]))

        def check(xxx_todo_changeme1):
            (bsid, brids) = xxx_todo_changeme1

            def thd(conn):
                self.assertEqual(len(brids), 2)

                # should see one buildset row
                r = conn.execute(self.db.model.buildsets.select())
                rows = [(row.id, row.external_idstring, row.reason,
                         row.complete, row.complete_at, row.results)
                        for row in r.fetchall()]
                self.assertEqual(rows,
                                 [(bsid, None, u'because', 0, None, -1)])

                # one property row
                r = conn.execute(self.db.model.buildset_properties.select())
                rows = [(row.buildsetid, row.property_name, row.property_value)
                        for row in r.fetchall()]
                self.assertEqual(rows,
                                 [(bsid, 'prop', json.dumps([['list'], 'test']))])

                # one buildset_sourcestamps row
                r = conn.execute(self.db.model.buildset_sourcestamps.select())
                rows = [(row.buildsetid, row.sourcestampid)
                        for row in r.fetchall()]
                self.assertEqual(rows, [(bsid, 234)])

                # and two buildrequests rows (and don't re-check the default
                # columns)
                r = conn.execute(self.db.model.buildrequests.select())
                rows = [(row.buildsetid, row.id, row.builderid)
                        for row in r.fetchall()]

                # we don't know which of the brids is assigned to which
                # buildername, but either one will do
                self.assertEqual(sorted(rows),
                                 [(bsid, brids[1], 1), (bsid, brids[2], 2)])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d


class TestFakeDB(unittest.TestCase, Tests):

    def setUp(self):
        self.master = fakemaster.make_master(wantDb=True, testcase=self)
        self.db = self.master.db
        self.db.checkForeignKeys = True
        self.insertTestData = self.db.insertTestData
        return self.setUpTests()

    def test_addBuildset_bad_waited_for(self):
        # only the fake db asserts on the type of waited_for
        d = self.db.buildsets.addBuildset(sourcestamps=[234], reason='because',
                                          properties={}, builderids=[1], external_idstring='extid',
                                          waited_for='wat', _reactor=self.clock)
        self.assertFailure(d, AssertionError)


class TestRealDB(db.TestCase,
                 connector_component.ConnectorComponentMixin,
                 RealTests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['patches', 'buildsets', 'buildset_properties',
                         'objects', 'buildrequests', 'sourcestamps',
                         'buildset_sourcestamps', 'builders',
                         'builds', 'masters', 'workers'])

        @d.addCallback
        def finish_setup(_):
            self.db.buildsets = buildsets.BuildsetsConnectorComponent(self.db)
        d.addCallback(lambda _: self.setUpTests())
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    @defer.inlineCallbacks
    def test_addBuildset_properties_cache(self):
        """
        Test that `addChange` properly seeds the `getChange` cache.
        """

        # Patchup the buildset properties cache so we can verify that
        # it got called form `addBuildset`.
        mockedCachePut = mock.Mock()
        self.patch(
            self.db.buildsets.getBuildsetProperties.cache,
            "put", mockedCachePut)

        # Setup a dummy set of properties to insert with the buildset.
        props = dict(prop=(['list'], 'test'))

        # Now, call `addBuildset`, and verify that the above properties
        # were seed in the `getBuildsetProperties` cache.
        bsid, _ = yield self.db.buildsets.addBuildset(
            sourcestamps=[234], reason='because',
            properties=props, builderids=[1, 2],
            waited_for=False)
        mockedCachePut.assert_called_once_with(bsid, props)
