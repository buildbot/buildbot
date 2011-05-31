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
import sqlalchemy as sa
from twisted.trial import unittest
from twisted.internet import task
from buildbot.db import buildrequests
from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb
from buildbot.util import UTC

class TestBuildsetsConnectorComponent(
            connector_component.ConnectorComponentMixin,
            unittest.TestCase):

    # test that the datetime translations are done correctly by specifying
    # the epoch timestamp and datetime objects explicitly.  These should
    # pass regardless of the local timezone used while running tests!
    CLAIMED_AT = datetime.datetime(1978, 6, 15, 12, 31, 15, tzinfo=UTC)
    CLAIMED_AT_EPOCH = 266761875
    SUBMITTED_AT = datetime.datetime(1979, 6, 15, 12, 31, 15, tzinfo=UTC)
    SUBMITTED_AT_EPOCH = 298297875
    COMPLETE_AT = datetime.datetime(1980, 6, 15, 12, 31, 15, tzinfo=UTC)
    COMPLETE_AT_EPOCH = 329920275
    BSID = 567
    BSID2 = 5670
    MASTER_NAME = "testmaster"
    MASTER_INCARN = "pid123-boot456789"

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=[ 'patches', 'changes', 'sourcestamp_changes',
                'buildsets', 'buildset_properties', 'buildrequests',
                'sourcestamps' ])

        def finish_setup(_):
            self.db.buildrequests = \
                    buildrequests.BuildRequestsConnectorComponent(self.db)
            self.db.master.master_name = self.MASTER_NAME
            self.db.master.master_incarnation = self.MASTER_INCARN
        d.addCallback(finish_setup)

        # set up a sourcestamp and buildset for use below
        d.addCallback(lambda _ :
            self.insertTestData([
                fakedb.SourceStamp(id=234),
                fakedb.Buildset(id=self.BSID, sourcestampid=234),
            ]))

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # test data

    # tests

    def test_getBuildRequest(self):
        d = self.insertTestData([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID, buildername="bbb",
                complete=1, results=75, priority=7,
                claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation=self.MASTER_INCARN,
                claimed_at=self.CLAIMED_AT_EPOCH,
                submitted_at=self.SUBMITTED_AT_EPOCH,
                complete_at=self.COMPLETE_AT_EPOCH),
        ])
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequest(44))
        def check(brdict):
            self.assertEqual(brdict,
                    dict(brid=44, buildsetid=self.BSID, buildername="bbb",
                        priority=7, claimed=True, mine=True, complete=True,
                        results=75, claimed_at=self.CLAIMED_AT,
                        submitted_at=self.SUBMITTED_AT,
                        complete_at=self.COMPLETE_AT))
        d.addCallback(check)
        return d

    def test_getBuildRequest_missing(self):
        d = self.db.buildrequests.getBuildRequest(44)
        def check(brdict):
            self.assertEqual(brdict, None)
        d.addCallback(check)
        return d

    def do_test_getBuildRequests_claim_args(self, **kwargs):
        expected = kwargs.pop('expected')
        d = self.insertTestData([
            # 50: claimed by this master
            fakedb.BuildRequest(id=50, buildsetid=self.BSID,
                claimed_at=self.CLAIMED_AT_EPOCH,
                claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation=self.MASTER_INCARN),
            # 51: claimed by another master
            fakedb.BuildRequest(id=51, buildsetid=self.BSID,
                claimed_at=self.CLAIMED_AT_EPOCH,
                claimed_by_name="other",
                claimed_by_incarnation="somepid-someboot"),
            # 52: unclaimed
            fakedb.BuildRequest(id=52, buildsetid=self.BSID,
                claimed_at=0, claimed_by_name=None,
                claimed_by_incarnation=None),
            # 53: unclaimed but complete (should not appear for claimed=False)
            fakedb.BuildRequest(id=53, buildsetid=self.BSID,
                claimed_at=0, claimed_by_name=None,
                claimed_by_incarnation=None,
                complete=1),
        ])
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequests(**kwargs))
        def check(brlist):
            self.assertEqual(sorted([ br['brid'] for br in brlist ]),
                             sorted(expected))
        d.addCallback(check)
        return d

    def test_getBuildRequests_no_claimed_arg(self):
        return self.do_test_getBuildRequests_claim_args(
                expected=[50, 51, 52, 53])

    def test_getBuildRequests_claimed_mine(self):
        return self.do_test_getBuildRequests_claim_args(
                claimed="mine",
                expected=[50])

    def test_getBuildRequests_claimed_true(self):
        return self.do_test_getBuildRequests_claim_args(
                claimed=True,
                expected=[50, 51])

    def test_getBuildRequests_unclaimed(self):
        return self.do_test_getBuildRequests_claim_args(
                claimed=False,
                expected=[52])

    def do_test_getBuildRequests_buildername_arg(self, **kwargs):
        expected = kwargs.pop('expected')
        d = self.insertTestData([
            # 8: 'bb'
            fakedb.BuildRequest(id=8, buildsetid=self.BSID, buildername='bb'),
            # 9: 'cc'
            fakedb.BuildRequest(id=9, buildsetid=self.BSID, buildername='cc'),
            # 10: 'cc'
            fakedb.BuildRequest(id=10, buildsetid=self.BSID, buildername='cc'),
        ])
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequests(**kwargs))
        def check(brlist):
            self.assertEqual(sorted([ br['brid'] for br in brlist ]),
                             sorted(expected))
        d.addCallback(check)
        return d

    def test_getBuildRequests_buildername_single(self):
        return self.do_test_getBuildRequests_buildername_arg(
                buildername='bb',
                expected=[8])

    def test_getBuildRequests_buildername_multiple(self):
        return self.do_test_getBuildRequests_buildername_arg(
                buildername='cc',
                expected=[9,10])

    def test_getBuildRequests_buildername_none(self):
        return self.do_test_getBuildRequests_buildername_arg(
                buildername='dd',
                expected=[])

    def do_test_getBuildRequests_complete_arg(self, **kwargs):
        expected = kwargs.pop('expected')
        d = self.insertTestData([
            # 70: incomplete
            fakedb.BuildRequest(id=70, buildsetid=self.BSID,
                complete=0, complete_at=None),
            # 80: complete
            fakedb.BuildRequest(id=80, buildsetid=self.BSID,
                complete=1,
                complete_at=self.COMPLETE_AT_EPOCH),
            # 81: complete but no complete_at
            fakedb.BuildRequest(id=81, buildsetid=self.BSID,
                complete=1, complete_at=0),
            # 82: complete_at set but complete is false, so not complete
            fakedb.BuildRequest(id=82, buildsetid=self.BSID,
                complete=0,
                complete_at=self.COMPLETE_AT_EPOCH),
        ])
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequests(**kwargs))
        def check(brlist):
            self.assertEqual(sorted([ br['brid'] for br in brlist ]),
                             sorted(expected))
        d.addCallback(check)
        return d

    def test_getBuildRequests_complete_none(self):
        return self.do_test_getBuildRequests_complete_arg(
                expected=[ 70, 80, 81, 82])

    def test_getBuildRequests_complete_true(self):
        return self.do_test_getBuildRequests_complete_arg(
                complete=True,
                expected=[ 80, 81 ])

    def test_getBuildRequests_complete_false(self):
        return self.do_test_getBuildRequests_complete_arg(
                complete=False,
                expected=[ 70, 82 ])

    def test_getBuildRequests_bsid_arg(self):
        d = self.insertTestData([
            # the buildset that we are *not* looking for
            fakedb.Buildset(id=self.BSID+1, sourcestampid=234),

            fakedb.BuildRequest(id=70, buildsetid=self.BSID,
                complete=0, complete_at=None),
            fakedb.BuildRequest(id=71, buildsetid=self.BSID+1,
                complete=0, complete_at=None),
            fakedb.BuildRequest(id=72, buildsetid=self.BSID,
                complete=0, complete_at=None),
        ])
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequests(bsid=self.BSID))
        def check(brlist):
            self.assertEqual(sorted([ br['brid'] for br in brlist ]),
                             sorted([70, 72]))
        d.addCallback(check)
        return d

    def test_getBuildRequests_combo(self):
        d = self.insertTestData([
            # 44: everything we want
            fakedb.BuildRequest(id=44, buildsetid=self.BSID, buildername="bbb",
                complete=1, results=92,
                complete_at=self.COMPLETE_AT_EPOCH,
                claimed_at=self.CLAIMED_AT_EPOCH,
                claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation=self.MASTER_INCARN),
            # 45: different buildername
            fakedb.BuildRequest(id=45, buildsetid=self.BSID, buildername="ccc",
                complete=1,
                complete_at=self.COMPLETE_AT_EPOCH,
                claimed_at=self.CLAIMED_AT_EPOCH,
                claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation=self.MASTER_INCARN),
            # 46: incomplete
            fakedb.BuildRequest(id=46, buildsetid=self.BSID, buildername="bbb",
                complete=0, results=92,
                complete_at=0,
                claimed_at=self.CLAIMED_AT_EPOCH,
                claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation=self.MASTER_INCARN),
            # 47: unclaimed
            fakedb.BuildRequest(id=47, buildsetid=self.BSID, buildername="bbb",
                complete=1, results=92,
                complete_at=self.COMPLETE_AT_EPOCH,
                claimed_at=0,
                claimed_by_name=None,
                claimed_by_incarnation=None),
            # 48: claimed by other
            fakedb.BuildRequest(id=48, buildsetid=self.BSID, buildername="bbb",
                complete=1, results=92,
                complete_at=self.COMPLETE_AT_EPOCH,
                claimed_at=self.CLAIMED_AT_EPOCH,
                claimed_by_name="other",
                claimed_by_incarnation="other"),
            # 49: different bsid
            fakedb.Buildset(id=self.BSID+1, sourcestampid=234),
            fakedb.BuildRequest(id=49, buildsetid=self.BSID+1,
                buildername="bbb", complete=1, results=92,
                complete_at=self.COMPLETE_AT_EPOCH,
                claimed_at=self.CLAIMED_AT_EPOCH,
                claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation=self.MASTER_INCARN),
        ])
        d.addCallback(lambda _ :
                self.db.buildrequests.getBuildRequests(buildername="bbb",
                    claimed="mine", complete=True, bsid=self.BSID))
        def check(brlist):
            self.assertEqual([ br['brid'] for br in brlist ], [ 44 ])
        d.addCallback(check)
        return d

    def do_test_claimBuildRequests(self, rows, now, brids, expected=None,
                                  expfailure=None, race_hook=None):
        clock = task.Clock()
        clock.advance(now)

        d = self.insertTestData(rows)
        d.addCallback(lambda _ :
            self.db.buildrequests.claimBuildRequests(brids=brids,
                        _reactor=clock, _race_hook=race_hook))
        def check(brlist):
            self.assertNotEqual(expected, None,
                    "unexpected success from claimBuildRequests")
            def thd(conn):
                tbl = self.db.model.buildrequests
                q = sa.select([ tbl.c.id, tbl.c.claimed_at,
                    tbl.c.claimed_by_name, tbl.c.claimed_by_incarnation ])
                results = conn.execute(q).fetchall()
                self.assertEqual(sorted(map(tuple, results)), sorted(expected))
            return self.db.pool.do(thd)
        d.addCallback(check)
        def fail(f):
            if not expfailure:
                raise f
            f.trap(expfailure)
        d.addErrback(fail)
        return d

    def test_claimBuildRequests_claimed_at_null(self):
        return self.do_test_claimBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                claimed_at=None, claimed_by_name=None,
                claimed_by_incarnation=None),
            ], 1300305712, [ 44 ],
            [ (44, 1300305712, self.MASTER_NAME, self.MASTER_INCARN) ])

    def test_claimBuildRequests_multiple(self):
        return self.do_test_claimBuildRequests([
                fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                    claimed_at=None, claimed_by_name=None,
                    claimed_by_incarnation=None),
                fakedb.BuildRequest(id=45, buildsetid=self.BSID,
                    claimed_at=None, claimed_by_name=None,
                    claimed_by_incarnation=None),
                fakedb.BuildRequest(id=46, buildsetid=self.BSID,
                    claimed_at=None, claimed_by_name=None,
                    claimed_by_incarnation=None),
            ], 1300305712, [ 44, 46 ],
            [
                (44, 1300305712, self.MASTER_NAME, self.MASTER_INCARN),
                (45, None, None, None),
                (46, 1300305712, self.MASTER_NAME, self.MASTER_INCARN),
            ])

    def test_claimBuildRequests_stress(self):
        return self.do_test_claimBuildRequests([
                fakedb.BuildRequest(id=id, buildsetid=self.BSID,
                    claimed_at=None, claimed_by_name=None,
                    claimed_by_incarnation=None)
                for id in xrange(1,1000)
            ], 1300305713, range(1, 1000),
            [
                (id, 1300305713, self.MASTER_NAME, self.MASTER_INCARN)
                for id in xrange(1, 1000)
            ])

    def test_claimBuildRequests_claimed_at_zero(self):
        return self.do_test_claimBuildRequests([
                fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                    claimed_at=0, claimed_by_name=None,
                    claimed_by_incarnation=None),
            ], 1300305712, [ 44 ],
            [ (44, 1300305712, self.MASTER_NAME, self.MASTER_INCARN) ])

    def test_claimBuildRequests_race(self):
        def race_hook(conn):
            q = self.db.model.buildrequests.update()
            conn.execute(q,
                    claimed_at=1298103810, claimed_by_name="interloper",
                    claimed_by_incarnation="re")
        return self.do_test_claimBuildRequests([
                fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                    claimed_at=0, claimed_by_name=None,
                    claimed_by_incarnation=None),
            ], 1300305712, [ 44 ],
            expfailure=buildrequests.AlreadyClaimedError,
            race_hook=race_hook)

    def test_claimBuildRequests_race_multiple(self):
        def race_hook(conn):
            tbl = self.db.model.buildrequests
            q = tbl.update(whereclause=(tbl.c.id == 45)) # only claim one BR
            conn.execute(q,
                    claimed_at=1298103810, claimed_by_name="interloper",
                    claimed_by_incarnation="re")
        d = self.do_test_claimBuildRequests([
                fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                    claimed_at=0, claimed_by_name=None,
                    claimed_by_incarnation=None),
                fakedb.BuildRequest(id=45, buildsetid=self.BSID,
                    claimed_at=0, claimed_by_name=None,
                    claimed_by_incarnation=None),
            ], 1300305712, [ 44, 45 ],
            expfailure=buildrequests.AlreadyClaimedError,
            race_hook=race_hook)
        # also check that we didn't keep a claim on 44 by looking again at
        # the set of claimed builds
        def check_claims(_):
            def thd(conn):
                tbl = self.db.model.buildrequests
                q = sa.select([ tbl.c.id, tbl.c.claimed_at,
                    tbl.c.claimed_by_name, tbl.c.claimed_by_incarnation ],
                    (tbl.c.claimed_at > 0))
                results = conn.execute(q).fetchall()
                self.assertEqual(map(tuple, results),
                        [ (45, 1298103810, 'interloper', 're') ])
            return self.db.pool.do(thd)
        d.addCallback(check_claims)
        return d

    def test_claimBuildRequests_reclaim(self):
        return self.do_test_claimBuildRequests([
                fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                    claimed_at=1300103810, claimed_by_name=self.MASTER_NAME,
                    claimed_by_incarnation=self.MASTER_INCARN),
            ], 1300305712, [ 44 ],
            # note that the time is updated
            [ (44, 1300305712, self.MASTER_NAME, self.MASTER_INCARN) ])

    def test_claimBuildRequests_reclaim_fail(self):
        d = self.do_test_claimBuildRequests([
                fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                    claimed_at=1300103810, claimed_by_name=self.MASTER_NAME,
                    claimed_by_incarnation=self.MASTER_INCARN),
                fakedb.BuildRequest(id=45, buildsetid=self.BSID,
                    claimed_at=1300103810, claimed_by_name="OTHER",
                    claimed_by_incarnation="01234"),
            ], 1300305712, [ 44, 45 ],
            expfailure=buildrequests.AlreadyClaimedError)
        def check(_):
            # check that the time wasn't updated on 44
            def thd(conn):
                if conn.engine.dialect.name == 'mysql':
                    # MySQL (with MyISAM tables) doesn't do rollback, so it
                    # can't satisfy this final check.  If you're using MySQL,
                    # deal with the incompatibilities :(
                    return
                tbl = self.db.model.buildrequests
                q = sa.select([ tbl.c.id, tbl.c.claimed_at,
                    tbl.c.claimed_by_name, tbl.c.claimed_by_incarnation ],
                    (tbl.c.claimed_at > 0),
                    order_by=tbl.c.id)
                results = conn.execute(q).fetchall()
                self.assertEqual(map(tuple, results), [
                        (44, 1300103810, self.MASTER_NAME, self.MASTER_INCARN),
                        (45, 1300103810, "OTHER", "01234"),
                    ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_claimBuildRequests_other_master_claim(self):
        return self.do_test_claimBuildRequests([
                fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                    claimed_at=1300103810, claimed_by_name="OTHER",
                    claimed_by_incarnation="0024-0935"),
            ], 1300305712, [ 44 ],
            expfailure=buildrequests.AlreadyClaimedError)

    def test_claimBuildRequests_other_master_claim_stress(self):
        d = self.do_test_claimBuildRequests([
                fakedb.BuildRequest(id=id, buildsetid=self.BSID,
                    claimed_at=0, claimed_by_name=None,
                    claimed_by_incarnation=None)
                for id in range(1, 1000) ] +
            [
                fakedb.BuildRequest(id=1000, buildsetid=self.BSID,
                    claimed_at=1300103810, claimed_by_name="OTHER",
                    claimed_by_incarnation="0024-0935"),
            ], 1300305712, range(1, 1001),
            expfailure=buildrequests.AlreadyClaimedError)
        def check(_):
            # check that [1,1000) were correctly unclaimed
            def thd(conn):
                tbl = self.db.model.buildrequests
                q = sa.select([ tbl.c.id, tbl.c.claimed_at,
                    tbl.c.claimed_by_name, tbl.c.claimed_by_incarnation ],
                    (tbl.c.claimed_at > 0),
                    order_by=tbl.c.id)
                results = conn.execute(q).fetchall()
                self.assertEqual(map(tuple, results),
                        [ (1000, 1300103810, 'OTHER', '0024-0935') ])
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_claimBuildRequests_other_incarn_claim(self):
        return self.do_test_claimBuildRequests([
                fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                    claimed_at=1300103810, claimed_by_name=self.MASTER_NAME,
                    claimed_by_incarnation="0024-0935"),
            ], 1300305712, [ 44 ],
            expfailure=buildrequests.AlreadyClaimedError)

    def test_claimBuildRequests_no_such(self):
        return self.do_test_claimBuildRequests([
                fakedb.BuildRequest(id=45, buildsetid=self.BSID),
            ], 1300305712, [ 44 ],
            expfailure=buildrequests.AlreadyClaimedError)

    def do_test_completeBuildRequests(self, rows, now, expected=None,
                                     expfailure=None, brids=[44]):
        clock = task.Clock()
        clock.advance(now)

        d = self.insertTestData(rows)
        d.addCallback(lambda _ :
            self.db.buildrequests.completeBuildRequests(brids=brids,
                                            results=7, _reactor=clock))
        def check(brlist):
            self.assertNotEqual(expected, None,
                    "unexpected success from completeBuildRequests")
            def thd(conn):
                tbl = self.db.model.buildrequests
                q = sa.select([ tbl.c.id, tbl.c.complete,
                                 tbl.c.results, tbl.c.complete_at ])
                results = conn.execute(q).fetchall()
                self.assertEqual(sorted(map(tuple, results)), sorted(expected))
            return self.db.pool.do(thd)
        d.addCallback(check)
        def fail(f):
            if not expfailure:
                raise f
            f.trap(expfailure)
        d.addErrback(fail)
        return d

    def test_completeBuildRequests(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                claimed_at=1300103810, claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation=self.MASTER_INCARN),
            ], 1300305712,
            [ (44, 1, 7, 1300305712) ])

    def test_completeBuildRequests_multiple(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                claimed_at=1300103810, claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation=self.MASTER_INCARN),
            fakedb.BuildRequest(id=45, buildsetid=self.BSID,
                claimed_at=1300103811, claimed_by_name="some other",
                claimed_by_incarnation="master"),
            fakedb.BuildRequest(id=46, buildsetid=self.BSID,
                claimed_at=1300103812, claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation=self.MASTER_INCARN),
            ], 1300305712,
            [ (44, 1, 7, 1300305712),
              (45, 0, -1, 0),
              (46, 1, 7, 1300305712),
            ], brids=[44, 46])

    def test_completeBuildRequests_multiple_notmine(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                claimed_at=1300103810, claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation=self.MASTER_INCARN),
            fakedb.BuildRequest(id=45, buildsetid=self.BSID,
                claimed_at=1300103811, claimed_by_name="some other",
                claimed_by_incarnation="master"),
            fakedb.BuildRequest(id=46, buildsetid=self.BSID,
                claimed_at=1300103812, claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation=self.MASTER_INCARN),
            ], 1300305712,
            brids=[44, 45, 46],
            expfailure=buildrequests.NotClaimedError)

    def test_completeBuildRequests_unclaimed(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                claimed_at=0, claimed_by_name=None,
                claimed_by_incarnation=None),
            ], 1300305712,
            expfailure=buildrequests.NotClaimedError)

    def test_completeBuildRequests_not_mine(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                claimed_at=1234, claimed_by_name="other",
                claimed_by_incarnation="other"),
            ], 1300305712,
            expfailure=buildrequests.NotClaimedError)

    def test_completeBuildRequests_already_completed(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                complete=1, complete_at=1300104190,
                claimed_at=1300103810, claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation=self.MASTER_INCARN),
            ], 1300305712,
            expfailure=buildrequests.NotClaimedError)

    def test_completeBuildRequests_no_such(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=45, buildsetid=self.BSID),
            ], 1300305712,
            expfailure=buildrequests.NotClaimedError)

    def do_test_unclaimMethod(self, method, expected):
        d = self.insertTestData([
            # 44: a complete build (should not be unclaimed)
            fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                complete=1, results=92,
                complete_at=self.COMPLETE_AT_EPOCH,
                claimed_at=self.CLAIMED_AT_EPOCH,
                claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation=self.MASTER_INCARN),
            # 45: incomplete build belonging to this incarnation
            fakedb.BuildRequest(id=45, buildsetid=self.BSID,
                complete=0,
                claimed_at=self.CLAIMED_AT_EPOCH,
                claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation=self.MASTER_INCARN),
            # 46: incomplete build belonging to another master
            fakedb.BuildRequest(id=46, buildsetid=self.BSID,
                complete=0,
                complete_at=0,
                claimed_at=self.CLAIMED_AT_EPOCH,
                claimed_by_name="other-master",
                claimed_by_incarnation="other-incarn"),
            # 47: unclaimed
            fakedb.BuildRequest(id=47, buildsetid=self.BSID,
                complete=0,
                complete_at=0,
                claimed_at=0,
                claimed_by_name=None,
                claimed_by_incarnation=None),
            # 48: claimed by previous incarnation, but recently
            fakedb.BuildRequest(id=48, buildsetid=self.BSID,
                complete=0,
                complete_at=0,
                claimed_at=self.CLAIMED_AT_EPOCH-50,
                claimed_by_name=self.MASTER_NAME,
                claimed_by_incarnation="other"),
            # 49: incomplete old build belonging to another master
            fakedb.BuildRequest(id=49, buildsetid=self.BSID,
                complete=0,
                complete_at=0,
                claimed_at=self.CLAIMED_AT_EPOCH - 1000,
                claimed_by_name="other-master",
                claimed_by_incarnation="other-incarn"),
        ])
        d.addCallback(lambda _ : method())
        def check(brlist):
            def thd(conn):
                tbl = self.db.model.buildrequests
                q = sa.select([ tbl.c.id ],
                        whereclause=(
                            (tbl.c.claimed_at == 0) &
                            (tbl.c.claimed_by_name == None) &
                            (tbl.c.claimed_by_incarnation == None)))
                results = conn.execute(q).fetchall()
                self.assertEqual(sorted([ r.id for r in results ]),
                                 sorted(expected))
            return self.db.pool.do(thd)
        d.addCallback(check)
        return d

    def test_unclaimOldIncarnationRequests(self):
        return self.do_test_unclaimMethod(
            self.db.buildrequests.unclaimOldIncarnationRequests,
            [47, 48])

    def test_unclaimExpiredRequests(self):
        clock = task.Clock()
        clock.advance(self.CLAIMED_AT_EPOCH)

        meth = self.db.buildrequests.unclaimExpiredRequests
        return self.do_test_unclaimMethod(
            lambda : meth(100, _reactor=clock),
            [47, 49])

    def test_unclaimBuildRequests(self):
        to_unclaim = [
            44, # completed -> not unclaimed
            45, # incomplete -> unclaimed
            46, # from another master -> not unclaimed
            47, # unclaimed -> still unclaimed
            48, # previous incarnation -> not unclaimed
            49, # another master -> not unclaimed
            50  # no such buildrequest -> no error
        ]
        return self.do_test_unclaimMethod(
            lambda : self.db.buildrequests.unclaimBuildRequests(to_unclaim),
            [45, 47])

