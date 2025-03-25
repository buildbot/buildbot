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

from buildbot import config
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.schedulers import base
from buildbot.schedulers import dependent
from buildbot.test import fakedb
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import scheduler
from buildbot.test.util.state import StateTestMixin

SUBMITTED_AT_TIME = 111111111
COMPLETE_AT_TIME = 222222222
OBJECTID = 33
SCHEDULERID = 133
UPSTREAM_NAME = 'uppy'


class Dependent(scheduler.SchedulerMixin, TestReactorMixin, StateTestMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        yield self.setUpScheduler()

    @defer.inlineCallbacks
    def makeScheduler(self, upstream=None):
        # build a fake upstream scheduler
        class Upstream(base.ReconfigurableBaseScheduler):
            def __init__(self, name):
                super().__init__(name=name, builderNames=['a'])

        if not upstream:
            upstream = Upstream(UPSTREAM_NAME)

        sched = dependent.Dependent(name='n', builderNames=['b'], upstream=upstream)
        yield self.attachScheduler(
            sched, OBJECTID, SCHEDULERID, overrideBuildsetMethods=True, createBuilderDB=True
        )

        return sched

    @defer.inlineCallbacks
    def assertBuildsetSubscriptions(self, bsids=None):
        yield self.assert_state(OBJECTID, upstream_bsids=bsids)

    # tests

    # NOTE: these tests take advantage of the fact that all of the fake
    # scheduler operations are synchronous, and thus do not return a Deferred.
    # The Deferred from trigger() is completely processed before this test
    # method returns.

    @defer.inlineCallbacks
    def test_constructor_string_arg(self):
        with self.assertRaises(config.ConfigErrors):
            yield self.makeScheduler(upstream='foo')

    @defer.inlineCallbacks
    def test_activate(self):
        sched = yield self.makeScheduler()
        yield self.master.startService()

        self.assertEqual(
            sorted([q.filter for q in sched.master.mq.qrefs]),
            [
                (
                    'buildsets',
                    None,
                    'complete',
                ),
                (
                    'buildsets',
                    None,
                    'new',
                ),
                ('schedulers', '133', 'updated'),
            ],
        )

        yield sched.deactivate()

        self.assertEqual(
            [q.filter for q in sched.master.mq.qrefs], [('schedulers', '133', 'updated')]
        )

    def sendBuildsetMessage(self, scheduler_name=None, results=-1, complete=False):
        """Call callConsumer with a buildset message.  Most of the values here
        are hard-coded to correspond to those in do_test."""
        msg = {
            "bsid": 44,
            "sourcestamps": [],  # blah blah blah
            "submitted_at": SUBMITTED_AT_TIME,
            "complete": complete,
            "complete_at": COMPLETE_AT_TIME if complete else None,
            "external_idstring": None,
            "reason": 'Because',
            "results": results if complete else -1,
            "parent_buildid": None,
            "parent_relationship": None,
        }
        if not complete:
            msg['scheduler'] = scheduler_name
        self.master.mq.callConsumer(('buildsets', '44', 'complete' if complete else 'new'), msg)

    @defer.inlineCallbacks
    def do_test(self, scheduler_name, expect_subscription, results, expect_buildset):
        """Test the dependent scheduler by faking a buildset and subsequent
        completion from an upstream scheduler.

        @param scheduler_name: upstream scheduler's name
        @param expect_subscription: whether to expect the dependent to
            subscribe to the buildset
        @param results: results of the upstream scheduler's buildset
        @param expect_buidlset: whether to expect the dependent to generate
            a new buildset in response
        """

        yield self.master.db.insert_test_data([
            fakedb.ObjectState(objectid=OBJECTID, name='upstream_bsids', value_json='[]'),
            fakedb.Object(id=OBJECTID),
        ])

        yield self.makeScheduler()
        yield self.master.startService()

        # announce a buildset with a matching name..
        yield self.master.db.insert_test_data([
            fakedb.SourceStamp(
                id=93,
                revision='555',
                branch='master',
                project='proj',
                repository='repo',
                codebase='cb',
            ),
            fakedb.Buildset(
                id=44,
                submitted_at=SUBMITTED_AT_TIME,
                complete=False,
                complete_at=None,
                external_idstring=None,
                reason='Because',
                results=-1,
            ),
            fakedb.BuildsetSourceStamp(buildsetid=44, sourcestampid=93),
        ])
        self.sendBuildsetMessage(scheduler_name=scheduler_name, complete=False)
        yield self.master.mq._deferwaiter.wait()

        # check whether scheduler is subscribed to that buildset
        if expect_subscription:
            yield self.assertBuildsetSubscriptions([44])
        else:
            yield self.assertBuildsetSubscriptions([])

        # pretend that the buildset is finished
        yield self.master.db.buildsets.completeBuildset(bsid=44, results=results)
        self.sendBuildsetMessage(results=results, complete=True)

        # and check whether a buildset was added in response
        if expect_buildset:
            self.assertEqual(
                self.addBuildsetCalls,
                [
                    (
                        'addBuildsetForSourceStamps',
                        {
                            "builderNames": None,  # defaults
                            "external_idstring": None,
                            "properties": None,
                            "reason": 'downstream',
                            "sourcestamps": [93],
                        },
                    ),
                ],
            )
        else:
            self.assertEqual(self.addBuildsetCalls, [])

    def test_related_buildset_SUCCESS(self):
        return self.do_test(UPSTREAM_NAME, True, SUCCESS, True)

    def test_related_buildset_WARNINGS(self):
        return self.do_test(UPSTREAM_NAME, True, WARNINGS, True)

    def test_related_buildset_FAILURE(self):
        return self.do_test(UPSTREAM_NAME, True, FAILURE, False)

    def test_unrelated_buildset(self):
        return self.do_test('unrelated', False, SUCCESS, False)

    @defer.inlineCallbacks
    def test_getUpstreamBuildsets_missing(self):
        sched = yield self.makeScheduler()

        # insert some state, with more bsids than exist
        yield self.master.db.insert_test_data([
            fakedb.SourceStamp(id=1234),
            fakedb.Buildset(id=11),
            fakedb.Buildset(id=13),
            fakedb.BuildsetSourceStamp(buildsetid=13, sourcestampid=1234),
            fakedb.Object(id=OBJECTID),
            fakedb.ObjectState(objectid=OBJECTID, name='upstream_bsids', value_json='[11,12,13]'),
        ])

        # check return value (missing 12)
        self.assertEqual(
            (yield sched._getUpstreamBuildsets()), [(11, [], False, -1), (13, [1234], False, -1)]
        )

        # and check that it wrote the correct value back to the state
        yield self.assert_state(OBJECTID, upstream_bsids=[11, 13])

    @defer.inlineCallbacks
    def test_enabled_callback(self):
        sched = yield self.makeScheduler()
        expectedValue = not sched.enabled
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, expectedValue)
        expectedValue = not sched.enabled
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, expectedValue)

    @defer.inlineCallbacks
    def test_disabled_activate(self):
        sched = yield self.makeScheduler()
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        r = yield sched.activate()
        self.assertEqual(r, None)

    @defer.inlineCallbacks
    def test_disabled_deactivate(self):
        sched = yield self.makeScheduler()
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        r = yield sched.deactivate()
        self.assertEqual(r, None)
