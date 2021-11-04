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
from twisted.trial import unittest

from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.schedulers.canceller_buildset import FailingBuildsetCanceller
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.util.ssfilter import SourceStampFilter


class TestOldBuildCanceller(TestReactorMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantMq=True, wantData=True, wantDb=True)
        self.master.mq.verifyMessages = False

        self.insert_test_data()
        self._cancelled_build_ids = []

        yield self.master.startService()

    def tearDown(self):
        return self.master.stopService()

    def insert_test_data(self):
        self.master.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Builder(id=100, name='builder1'),
            fakedb.Builder(id=101, name='builder2'),
            fakedb.Builder(id=102, name='builder3'),

            fakedb.Buildset(id=200, results=None, reason="reason98"),
            fakedb.BuildsetSourceStamp(buildsetid=200, sourcestampid=300),
            fakedb.SourceStamp(id=300, revision='revision1', project='project1',
                               codebase='codebase1', repository='repository1', branch='branch1'),

            fakedb.BuildRequest(id=400, buildsetid=200, builderid=100),
            fakedb.BuildRequestClaim(brid=400, masterid=92, claimed_at=1),
            fakedb.Build(id=500, number=1, builderid=100, buildrequestid=400, workerid=13,
                         masterid=92, results=None, state_string="state1"),

            fakedb.BuildRequest(id=401, buildsetid=200, builderid=101),
            fakedb.BuildRequestClaim(brid=401, masterid=92, claimed_at=1),
            fakedb.Build(id=501, number=1, builderid=101, buildrequestid=401, workerid=13,
                         masterid=92, results=None, state_string="state2"),

            fakedb.BuildRequest(id=402, buildsetid=200, builderid=102),
            fakedb.BuildRequestClaim(brid=402, masterid=92, claimed_at=1),
            fakedb.Build(id=502, number=1, builderid=102, buildrequestid=402, workerid=13,
                         masterid=92, results=None, state_string="state3"),
        ])

    def assert_cancelled(self, cancellations):
        expected_productions = []
        for build_id in cancellations:
            reason = 'Build has been cancelled because another build in the same buildset failed'

            expected_productions.append(
                (('control', 'builds', str(build_id), 'stop'),
                 {'reason': reason}))

        self.master.mq.assertProductions(expected_productions)

    @defer.inlineCallbacks
    def send_build_finished(self, id, results):
        build = yield self.master.data.get(('builds', str(id)))
        build['results'] = results
        self.master.mq.callConsumer(('builds', str(id), 'finished'), build)

    @defer.inlineCallbacks
    def test_cancel_buildrequests_ss_filter_does_not_match(self):
        self.canceller = FailingBuildsetCanceller('canceller', [
            (['builder1'], ['builder1', 'builder2', 'builder3'],
             SourceStampFilter(branch_eq=['branch_other'])),
        ])
        yield self.canceller.setServiceParent(self.master)
        yield self.send_build_finished(500, FAILURE)
        self.assert_cancelled([])

    @defer.inlineCallbacks
    def test_cancel_buildrequests_builder_filter_does_not_match(self):
        self.canceller = FailingBuildsetCanceller('canceller', [
            (['builder2'], ['builder1', 'builder2', 'builder3'],
             SourceStampFilter(branch_eq=['branch1'])),
        ])
        yield self.canceller.setServiceParent(self.master)
        yield self.send_build_finished(500, FAILURE)
        self.assert_cancelled([])

    @defer.inlineCallbacks
    def test_cancel_buildrequests_not_failure(self):
        self.canceller = FailingBuildsetCanceller('canceller', [
            (['builder1'], ['builder1', 'builder2', 'builder3'],
             SourceStampFilter(branch_eq=['branch1'])),
        ])
        yield self.canceller.setServiceParent(self.master)
        yield self.send_build_finished(500, SUCCESS)
        self.assert_cancelled([])

    @defer.inlineCallbacks
    def test_cancel_buildrequests_matches(self):
        self.canceller = FailingBuildsetCanceller('canceller', [
            (['builder1'], ['builder1', 'builder2', 'builder3'],
             SourceStampFilter(branch_eq=['branch1'])),
        ])
        yield self.canceller.setServiceParent(self.master)
        yield self.send_build_finished(500, FAILURE)
        self.assert_cancelled([501, 502])

    @defer.inlineCallbacks
    def test_cancel_buildrequests_matches_any_builder(self):
        self.canceller = FailingBuildsetCanceller('canceller', [
            (['builder1'], None, SourceStampFilter(branch_eq=['branch1'])),
        ])
        yield self.canceller.setServiceParent(self.master)
        yield self.send_build_finished(500, FAILURE)
        self.assert_cancelled([501, 502])
