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

from buildbot.db import buildrequests
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util import connector_component
from buildbot.test.util import db
from buildbot.test.util import interfaces
from buildbot.util import UTC
from buildbot.util import epoch2datetime
from twisted.internet import task
from twisted.trial import unittest


class Tests(interfaces.InterfaceTests):
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
    MASTER_ID = "set in setUpTests"
    OTHER_MASTER_ID = "set in setUpTests"
    MASTER_NAME = "testmaster"
    MASTER_INCARN = "pid123-boot456789"

    def setUpTests(self):
        # set up a sourcestamp and buildset for use below
        self.MASTER_ID = fakedb.FakeBuildRequestsComponent.MASTER_ID
        self.OTHER_MASTER_ID = self.MASTER_ID + 1111

        return self.insertTestData([
            fakedb.SourceStampSet(id=234),
            fakedb.SourceStamp(id=234, sourcestampsetid=234),
            fakedb.Object(id=self.MASTER_ID, name="fake master",
                          class_name="BuildMaster"),
            fakedb.Object(id=self.OTHER_MASTER_ID, name="other master",
                          class_name="BuildMaster"),
            fakedb.Buildset(id=self.BSID, sourcestampsetid=234),
        ])

    # tests

    def test_getBuildRequest(self):
        d = self.insertTestData([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID, buildername="bbb",
                                complete=1, results=75, priority=7,
                                submitted_at=self.SUBMITTED_AT_EPOCH,
                                complete_at=self.COMPLETE_AT_EPOCH),
            fakedb.BuildRequestClaim(
                brid=44, objectid=self.MASTER_ID,
                claimed_at=self.CLAIMED_AT_EPOCH),
        ])
        d.addCallback(lambda _:
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
            fakedb.BuildRequest(id=50, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=50, objectid=self.MASTER_ID,
                                     claimed_at=self.CLAIMED_AT_EPOCH),

            # 51: claimed by another master
            fakedb.BuildRequest(id=51, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=51, objectid=self.OTHER_MASTER_ID,
                                     claimed_at=self.CLAIMED_AT_EPOCH),

            # 52: unclaimed
            fakedb.BuildRequest(id=52, buildsetid=self.BSID),

            # 53: unclaimed but complete (should not appear for claimed=False)
            fakedb.BuildRequest(id=53, buildsetid=self.BSID, complete=1),
        ])
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests(**kwargs))

        def check(brlist):
            self.assertEqual(sorted([br['brid'] for br in brlist]),
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
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests(**kwargs))

        def check(brlist):
            self.assertEqual(sorted([br['brid'] for br in brlist]),
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
            expected=[9, 10])

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
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests(**kwargs))

        def check(brlist):
            self.assertEqual(sorted([br['brid'] for br in brlist]),
                             sorted(expected))
        d.addCallback(check)
        return d

    def test_getBuildRequests_complete_none(self):
        return self.do_test_getBuildRequests_complete_arg(
            expected=[70, 80, 81, 82])

    def test_getBuildRequests_complete_true(self):
        return self.do_test_getBuildRequests_complete_arg(
            complete=True,
            expected=[80, 81])

    def test_getBuildRequests_complete_false(self):
        return self.do_test_getBuildRequests_complete_arg(
            complete=False,
            expected=[70, 82])

    def test_getBuildRequests_bsid_arg(self):
        d = self.insertTestData([
            # the buildset that we are *not* looking for
            fakedb.Buildset(id=self.BSID + 1, sourcestampsetid=234),

            fakedb.BuildRequest(id=70, buildsetid=self.BSID,
                                complete=0, complete_at=None),
            fakedb.BuildRequest(id=71, buildsetid=self.BSID + 1,
                                complete=0, complete_at=None),
            fakedb.BuildRequest(id=72, buildsetid=self.BSID,
                                complete=0, complete_at=None),
        ])
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests(bsid=self.BSID))

        def check(brlist):
            self.assertEqual(sorted([br['brid'] for br in brlist]),
                             sorted([70, 72]))
        d.addCallback(check)
        return d

    def test_getBuildRequests_combo(self):
        d = self.insertTestData([
            # 44: everything we want
            fakedb.BuildRequest(id=44, buildsetid=self.BSID, buildername="bbb",
                                complete=1, results=92,
                                complete_at=self.COMPLETE_AT_EPOCH),
            fakedb.BuildRequestClaim(brid=44, objectid=self.MASTER_ID,
                                     claimed_at=self.CLAIMED_AT_EPOCH),

            # 45: different buildername
            fakedb.BuildRequest(id=45, buildsetid=self.BSID, buildername="ccc",
                                complete=1,
                                complete_at=self.COMPLETE_AT_EPOCH),
            fakedb.BuildRequestClaim(brid=45, objectid=self.MASTER_ID,
                                     claimed_at=self.CLAIMED_AT_EPOCH),

            # 46: incomplete
            fakedb.BuildRequest(id=46, buildsetid=self.BSID, buildername="bbb",
                                complete=0, results=92,
                                complete_at=0),
            fakedb.BuildRequestClaim(brid=46, objectid=self.MASTER_ID,
                                     claimed_at=self.CLAIMED_AT_EPOCH),

            # 47: unclaimed
            fakedb.BuildRequest(id=47, buildsetid=self.BSID, buildername="bbb",
                                complete=1, results=92,
                                complete_at=self.COMPLETE_AT_EPOCH),

            # 48: claimed by other
            fakedb.BuildRequest(id=48, buildsetid=self.BSID, buildername="bbb",
                                complete=1, results=92,
                                complete_at=self.COMPLETE_AT_EPOCH),
            fakedb.BuildRequestClaim(brid=48, objectid=self.OTHER_MASTER_ID,
                                     claimed_at=self.CLAIMED_AT_EPOCH),

            # 49: different bsid
            fakedb.Buildset(id=self.BSID + 1, sourcestampsetid=234),
            fakedb.BuildRequest(id=49, buildsetid=self.BSID + 1,
                                buildername="bbb", complete=1, results=92,
                                complete_at=self.COMPLETE_AT_EPOCH),
            fakedb.BuildRequestClaim(brid=49, objectid=self.MASTER_ID,
                                     claimed_at=self.CLAIMED_AT_EPOCH),
        ])
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests(buildername="bbb",
                                                             claimed="mine", complete=True, bsid=self.BSID))

        def check(brlist):
            self.assertEqual([br['brid'] for br in brlist], [44])
        d.addCallback(check)
        return d

    def do_test_getBuildRequests_branch_arg(self, **kwargs):
        expected = kwargs.pop('expected')
        d = self.insertTestData([
            fakedb.BuildRequest(id=70, buildsetid=self.BSID + 1),
            fakedb.Buildset(id=self.BSID + 1, sourcestampsetid=self.BSID + 1),
            fakedb.SourceStampSet(id=self.BSID + 1),
            fakedb.SourceStamp(sourcestampsetid=self.BSID + 1,
                               branch='branch_A'),

            fakedb.BuildRequest(id=80, buildsetid=self.BSID + 2),
            fakedb.Buildset(id=self.BSID + 2, sourcestampsetid=self.BSID + 2),
            fakedb.SourceStampSet(id=self.BSID + 2),
            fakedb.SourceStamp(sourcestampsetid=self.BSID + 2,
                               repository='repository_A'),

            fakedb.BuildRequest(id=90, buildsetid=self.BSID + 3),
            fakedb.Buildset(id=self.BSID + 3, sourcestampsetid=self.BSID + 3),
            fakedb.SourceStampSet(id=self.BSID + 3),
            fakedb.SourceStamp(sourcestampsetid=self.BSID + 3,
                               branch='branch_A', repository='repository_A'),
        ])
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests(**kwargs))

        def check(brlist):
            self.assertEqual(sorted([br['brid'] for br in brlist]),
                             sorted(expected))
        d.addCallback(check)
        return d

    def test_getBuildRequests_branch(self):
        return self.do_test_getBuildRequests_branch_arg(branch='branch_A',
                                                        expected=[70, 90])

    def test_getBuildRequests_branch_empty(self):
        return self.do_test_getBuildRequests_branch_arg(branch='absent_branch',
                                                        expected=[])

    def test_getBuildRequests_repository(self):
        return self.do_test_getBuildRequests_branch_arg(
            repository='repository_A', expected=[80, 90])

    def test_getBuildRequests_repository_empty(self):
        return self.do_test_getBuildRequests_branch_arg(
            repository='absent_repository', expected=[])

    def test_getBuildRequests_repository_and_branch(self):
        return self.do_test_getBuildRequests_branch_arg(
            repository='repository_A', branch='branch_A', expected=[90])

    def test_getBuildRequests_no_repository_nor_branch(self):
        return self.do_test_getBuildRequests_branch_arg(expected=[70, 80, 90])

    def do_test_claimBuildRequests(self, rows, now, brids, expected=None,
                                   expfailure=None, claimed_at=None):
        clock = task.Clock()
        clock.advance(now)

        d = self.insertTestData(rows)
        d.addCallback(lambda _:
                      self.db.buildrequests.claimBuildRequests(brids=brids,
                                                               claimed_at=claimed_at, _reactor=clock))
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests())

        def check(results):
            self.assertNotEqual(expected, None,
                                "unexpected success from claimBuildRequests")
            self.assertEqual(
                sorted([(r['brid'], r['claimed_at'], r['mine'])
                        for r in results]),
                sorted(expected))
        d.addCallback(check)

        def fail(f):
            if not expfailure:
                raise f
            f.trap(expfailure)
        d.addErrback(fail)
        return d

    def test_claimBuildRequests_single(self):
        return self.do_test_claimBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
        ], 1300305712, [44],
            [(44, epoch2datetime(1300305712), True)])

    def test_claimBuildRequests_single_explicit_claimed_at(self):
        return self.do_test_claimBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
        ], 1300305712, [44],
            [(44, epoch2datetime(14000000), True)],
            claimed_at=epoch2datetime(14000000))

    def test_claimBuildRequests_multiple(self):
        return self.do_test_claimBuildRequests(
            [
                fakedb.BuildRequest(id=44, buildsetid=self.BSID),
                fakedb.BuildRequest(id=45, buildsetid=self.BSID),
                fakedb.BuildRequest(id=46, buildsetid=self.BSID),
            ],
            1300305712, [44, 46],
            [
                (44, epoch2datetime(1300305712), True),
                (45, None, False),
                (46, epoch2datetime(1300305712), True),
            ]
        )

    def test_claimBuildRequests_stress(self):
        return self.do_test_claimBuildRequests(
            [
                fakedb.BuildRequest(id=id, buildsetid=self.BSID)
                for id in xrange(1, 1000)
            ],
            1300305713, range(1, 1000),
            [
                (id, epoch2datetime(1300305713), True)
                for id in xrange(1, 1000)
            ]
        )

    def test_claimBuildRequests_other_master_claim(self):
        return self.do_test_claimBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=44,
                                     objectid=self.OTHER_MASTER_ID,
                                     claimed_at=1300103810),
        ], 1300305712, [44],
            expfailure=buildrequests.AlreadyClaimedError)

    @db.skip_for_dialect('mysql')
    def test_claimBuildRequests_other_master_claim_stress(self):
        d = self.do_test_claimBuildRequests(
            [fakedb.BuildRequest(id=id, buildsetid=self.BSID)
             for id in range(1, 1000)] +
            [
                fakedb.BuildRequest(id=1000, buildsetid=self.BSID),
                # the fly in the ointment..
                fakedb.BuildRequestClaim(brid=1000,
                                         objectid=self.OTHER_MASTER_ID, claimed_at=1300103810),
            ], 1300305712, range(1, 1001),
            expfailure=buildrequests.AlreadyClaimedError)
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests(claimed=True))

        def check(results):
            # check that [1,1000) were not claimed, and 1000 is still claimed
            self.assertEqual([
                (r['brid'], r['mine'], r['claimed_at'])
                for r in results
            ][:10], [
                (1000, False, epoch2datetime(1300103810))
            ])
        d.addCallback(check)
        return d

    def test_claimBuildRequests_sequential(self):
        now = 120350934
        clock = task.Clock()
        clock.advance(now)

        d = self.insertTestData([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
            fakedb.BuildRequest(id=45, buildsetid=self.BSID),
        ])
        d.addCallback(lambda _:
                      self.db.buildrequests.claimBuildRequests(brids=[44],
                                                               _reactor=clock))
        d.addCallback(lambda _:
                      self.db.buildrequests.claimBuildRequests(brids=[45],
                                                               _reactor=clock))
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests(claimed=False))

        def check(results):
            self.assertEqual(results, [])
        d.addCallback(check)
        return d

    def do_test_reclaimBuildRequests(self, rows, now, brids, expected=None,
                                     expfailure=None):
        clock = task.Clock()
        clock.advance(now)

        d = self.insertTestData(rows)
        d.addCallback(lambda _:
                      self.db.buildrequests.reclaimBuildRequests(brids=brids,
                                                                 _reactor=clock))
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests())

        def check(results):
            self.assertNotEqual(expected, None,
                                "unexpected success from claimBuildRequests")
            self.assertEqual(
                sorted([
                    (r['brid'], r['claimed_at'], r['mine'])
                    for r in results
                ]),
                sorted(expected)
            )
        d.addCallback(check)

        def fail(f):
            if not expfailure:
                raise f
            f.trap(expfailure)
        d.addErrback(fail)
        return d

    def test_reclaimBuildRequests(self):
        return self.do_test_reclaimBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=44, objectid=self.MASTER_ID,
                                     claimed_at=1300103810),
        ], 1300305712, [44],
            # note that the time is updated
            [(44, epoch2datetime(1300305712), True)])

    def test_reclaimBuildRequests_fail(self):
        d = self.do_test_reclaimBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=44, objectid=self.MASTER_ID,
                                     claimed_at=1300103810),
            fakedb.BuildRequest(id=45, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=45, objectid=self.OTHER_MASTER_ID,
                                     claimed_at=1300103810),
        ], 1300305712, [44, 45],
            expfailure=buildrequests.AlreadyClaimedError)

        # check that the time wasn't updated on 44, noting that MySQL does
        # not support this.
        if self.db_engine.dialect.name == 'mysql':
            return d

        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests())

        def check(results):
            self.assertEqual(sorted(
                (r['brid'], r['claimed_at'], r['mine'])
                for r in results
            ), [
                (44, epoch2datetime(1300103810), True),
                (45, epoch2datetime(1300103810), False),
            ])
        d.addCallback(check)
        return d

    def do_test_completeBuildRequests(self, rows, now, expected=None,
                                      expfailure=None, brids=[44],
                                      complete_at=None):
        clock = task.Clock()
        clock.advance(now)

        d = self.insertTestData(rows)
        d.addCallback(lambda _:
                      self.db.buildrequests.completeBuildRequests(brids=brids,
                                                                  results=7, complete_at=complete_at,
                                                                  _reactor=clock))
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests())

        def check(results):
            self.assertNotEqual(expected, None,
                                "unexpected success from completeBuildRequests")
            self.assertEqual(sorted(
                (r['brid'], r['complete'], r['results'], r['complete_at'])
                for r in results
            ), sorted(expected))
        d.addCallback(check)

        def fail(f):
            if not expfailure:
                raise f
            f.trap(expfailure)
        d.addErrback(fail)
        return d

    def test_completeBuildRequests(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=44, objectid=self.MASTER_ID,
                                     claimed_at=1300103810),
        ], 1300305712,
            [(44, True, 7, epoch2datetime(1300305712))])

    def test_completeBuildRequests_explicit_time(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=44, objectid=self.MASTER_ID,
                                     claimed_at=1300103810),
        ], 1300305712,
            [(44, True, 7, epoch2datetime(999999))],
            complete_at=epoch2datetime(999999))

    def test_completeBuildRequests_multiple(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=44, objectid=self.MASTER_ID,
                                     claimed_at=1300103810),
            fakedb.BuildRequest(id=45, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=45, objectid=self.OTHER_MASTER_ID,
                                     claimed_at=1300103811),
            fakedb.BuildRequest(id=46, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=46, objectid=self.MASTER_ID,
                                     claimed_at=1300103812),
        ], 1300305712,
            [(44, True, 7, epoch2datetime(1300305712)),
             (45, False, -1, None),
             (46, True, 7, epoch2datetime(1300305712)),
             ], brids=[44, 46])

    def test_completeBuildRequests_stress(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=id, buildsetid=self.BSID)
            for id in range(1, 280)
        ] + [
            fakedb.BuildRequestClaim(brid=id, objectid=self.MASTER_ID,
                                     claimed_at=1300103810)
            for id in range(1, 280)
        ], 1300305712,
            [(id, True, 7, epoch2datetime(1300305712))
                for id in range(1, 280)
             ], brids=range(1, 280))

    def test_completeBuildRequests_multiple_notmine(self):
        # note that the requests are completed even though they are not mine!
        return self.do_test_completeBuildRequests([
            # two unclaimed requests
            fakedb.BuildRequest(id=44, buildsetid=self.BSID),
            fakedb.BuildRequest(id=45, buildsetid=self.BSID),
            # and one claimed by another master
            fakedb.BuildRequest(id=46, buildsetid=self.BSID),
            fakedb.BuildRequestClaim(brid=46, objectid=self.OTHER_MASTER_ID,
                                     claimed_at=1300103812),
        ], 1300305712,
            [(44, True, 7, epoch2datetime(1300305712)),
             (45, True, 7, epoch2datetime(1300305712)),
             (46, True, 7, epoch2datetime(1300305712)), ],
            brids=[44, 45, 46])

    def test_completeBuildRequests_already_completed(self):
        return self.do_test_completeBuildRequests([
            fakedb.BuildRequest(id=44, buildsetid=self.BSID,
                                complete=1, complete_at=1300104190),
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
                                complete_at=self.COMPLETE_AT_EPOCH),
            fakedb.BuildRequestClaim(brid=44, objectid=self.MASTER_ID,
                                     claimed_at=self.CLAIMED_AT_EPOCH),

            # 45: incomplete build belonging to this incarnation
            fakedb.BuildRequest(id=45, buildsetid=self.BSID,
                                complete=0, complete_at=0),
            fakedb.BuildRequestClaim(brid=45, objectid=self.MASTER_ID,
                                     claimed_at=self.CLAIMED_AT_EPOCH),

            # 46: incomplete build belonging to another master
            fakedb.BuildRequest(id=46, buildsetid=self.BSID,
                                complete=0, complete_at=0),
            fakedb.BuildRequestClaim(brid=46, objectid=self.OTHER_MASTER_ID,
                                     claimed_at=self.CLAIMED_AT_EPOCH),

            # 47: unclaimed
            fakedb.BuildRequest(id=47, buildsetid=self.BSID,
                                complete=0, complete_at=0),

            # 48: claimed by this master, but recently
            fakedb.BuildRequest(id=48, buildsetid=self.BSID,
                                complete=0, complete_at=0),
            fakedb.BuildRequestClaim(brid=48, objectid=self.MASTER_ID,
                                     claimed_at=self.CLAIMED_AT_EPOCH - 50),

            # 49: incomplete old build belonging to another master
            fakedb.BuildRequest(id=49, buildsetid=self.BSID,
                                complete=0, complete_at=0),
            fakedb.BuildRequestClaim(brid=49, objectid=self.OTHER_MASTER_ID,
                                     claimed_at=self.CLAIMED_AT_EPOCH - 1000),
        ])
        d.addCallback(lambda _: method())
        # just select the unclaimed requests
        d.addCallback(lambda _:
                      self.db.buildrequests.getBuildRequests(claimed=False))

        def check(results):
            self.assertEqual(sorted([r['brid'] for r in results]),
                             sorted(expected))
        d.addCallback(check)
        return d

    def test_unclaimExpiredRequests(self):
        clock = task.Clock()
        clock.advance(self.CLAIMED_AT_EPOCH)

        meth = self.db.buildrequests.unclaimExpiredRequests
        return self.do_test_unclaimMethod(
            lambda: meth(100, _reactor=clock),
            [47, 49])

    def test_unclaimBuildRequests(self):
        to_unclaim = [
            44,  # completed -> should not be unclaimed
            45,  # incomplete -> unclaimed
            46,  # from another master -> not unclaimed
            47,  # unclaimed -> still unclaimed
            48,  # claimed -> unclaimed
            49,  # another master -> not unclaimed
            50  # no such buildrequest -> no error
        ]
        return self.do_test_unclaimMethod(
            lambda: self.db.buildrequests.unclaimBuildRequests(to_unclaim),
            [45, 47, 48])


class TestFakeDB(unittest.TestCase, Tests):
    # Compatiblity with some checks in the "real" tests.

    class db_engine:

        class dialect:
            name = 'buildbot_fake'

    def setUp(self):
        self.master = fakemaster.make_master(wantDb=True, testcase=self)
        self.db = self.master.db
        self.insertTestData = self.db.insertTestData
        return self.setUpTests()


class TestRealDB(unittest.TestCase,
                 connector_component.ConnectorComponentMixin,
                 Tests):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['patches', 'changes', 'sourcestamp_changes',
                         'buildsets', 'buildset_properties', 'buildrequests',
                         'objects', 'buildrequest_claims', 'sourcestamps', 'sourcestampsets'])

        @d.addCallback
        def finish_setup(_):
            self.db.buildrequests = \
                buildrequests.BuildRequestsConnectorComponent(self.db)
        d.addCallback(lambda _: self.setUpTests())
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()
