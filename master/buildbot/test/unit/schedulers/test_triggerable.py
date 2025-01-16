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
from twisted.python import log
from twisted.trial import unittest

from buildbot.db.buildrequests import BuildRequestModel
from buildbot.db.buildsets import BuildSetModel
from buildbot.process import properties
from buildbot.schedulers import triggerable
from buildbot.test import fakedb
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import interfaces
from buildbot.test.util import scheduler


class TriggerableInterfaceTest(unittest.TestCase, interfaces.InterfaceTests):
    def test_interface(self):
        self.assertInterfacesImplemented(triggerable.Triggerable)


class Triggerable(scheduler.SchedulerMixin, TestReactorMixin, unittest.TestCase):
    OBJECTID = 33
    SCHEDULERID = 13

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        # Necessary to get an assertable submitted_at time.
        self.reactor.advance(946684799)

        yield self.setUpScheduler()
        self.subscription = None

    @defer.inlineCallbacks
    def makeScheduler(self, overrideBuildsetMethods=False, **kwargs):
        yield self.master.db.insert_test_data([fakedb.Builder(id=77, name='b')])

        sched = yield self.attachScheduler(
            triggerable.Triggerable(name='n', builderNames=['b'], **kwargs),
            self.OBJECTID,
            self.SCHEDULERID,
            overrideBuildsetMethods=overrideBuildsetMethods,
        )

        return sched

    @defer.inlineCallbacks
    def assertTriggeredBuildset(self, idsDeferred, waited_for, properties=None, sourcestamps=None):
        if properties is None:
            properties = {}
        bsid, brids = yield idsDeferred
        properties.update({'scheduler': ('n', 'Scheduler')})

        buildset = yield self.master.db.buildsets.getBuildset(bsid)
        got_properties = yield self.master.db.buildsets.getBuildsetProperties(bsid)
        self.assertEqual(got_properties, properties)

        from datetime import datetime

        from buildbot.util import UTC

        self.assertEqual(
            buildset,
            BuildSetModel(
                bsid=bsid,
                external_idstring=None,
                reason="The Triggerable scheduler named 'n' triggered this build",
                submitted_at=datetime(1999, 12, 31, 23, 59, 59, tzinfo=UTC),
                results=-1,
                # sourcestamps testing is just after
                sourcestamps=buildset.sourcestamps,
            ),
        )

        actual_sourcestamps = yield defer.gatherResults(
            [self.master.db.sourcestamps.getSourceStamp(ssid) for ssid in buildset.sourcestamps],
            consumeErrors=True,
        )

        self.assertEqual(len(sourcestamps), len(actual_sourcestamps))
        for expected_ss, actual_ss in zip(sourcestamps, actual_sourcestamps):
            # We don't care if the actual sourcestamp has *more* attributes
            # than expected.
            self.assertEqual(expected_ss, {k: getattr(actual_ss, k) for k in expected_ss.keys()})

        for brid in brids.values():
            buildrequest = yield self.master.db.buildrequests.getBuildRequest(brid)
            self.assertEqual(
                buildrequest,
                BuildRequestModel(
                    buildrequestid=brid,
                    buildername='b',
                    builderid=77,
                    buildsetid=bsid,
                    claimed_at=None,
                    complete=False,
                    complete_at=None,
                    claimed_by_masterid=None,
                    priority=0,
                    results=-1,
                    submitted_at=datetime(1999, 12, 31, 23, 59, 59, tzinfo=UTC),
                    waited_for=waited_for,
                ),
            )

        return bsid

    def sendCompletionMessage(self, bsid, results=3):
        self.master.mq.callConsumer(
            ('buildsets', str(bsid), 'complete'),
            {
                "bsid": bsid,
                "submitted_at": 100,
                "complete": True,
                "complete_at": 200,
                "external_idstring": None,
                "reason": 'triggering',
                "results": results,
                "sourcestamps": [],
                "parent_buildid": None,
                "parent_relationship": None,
            },
        )

    # tests

    # NOTE: these tests take advantage of the fact that all of the fake
    # scheduler operations are synchronous, and thus do not return a Deferred.
    # The Deferred from trigger() is completely processed before this test
    # method returns.

    @defer.inlineCallbacks
    def test_constructor_no_reason(self):
        sched = yield self.makeScheduler()
        yield sched.configureService()
        self.assertEqual(sched.reason, None)  # default reason is dynamic

    @defer.inlineCallbacks
    def test_constructor_explicit_reason(self):
        sched = yield self.makeScheduler(reason="Because I said so")
        yield sched.configureService()
        self.assertEqual(sched.reason, "Because I said so")

    @defer.inlineCallbacks
    def test_constructor_priority_none(self):
        sched = yield self.makeScheduler(priority=None)
        yield sched.configureService()
        self.assertEqual(sched.priority, None)

    @defer.inlineCallbacks
    def test_constructor_priority_int(self):
        sched = yield self.makeScheduler(priority=8)
        yield sched.configureService()
        self.assertEqual(sched.priority, 8)

    @defer.inlineCallbacks
    def test_constructor_priority_function(self):
        def sched_priority(builderNames, changesByCodebase):
            return 0

        sched = yield self.makeScheduler(priority=sched_priority)
        yield sched.configureService()
        self.assertEqual(sched.priority, sched_priority)

    @defer.inlineCallbacks
    def test_trigger(self):
        sched = yield self.makeScheduler(codebases={'cb': {'repository': 'r'}})

        # no subscription should be in place yet
        self.assertEqual(sched.master.mq.qrefs, [])

        yield self.master.startService()

        # trigger the scheduler, exercising properties while we're at it
        waited_for = True
        set_props = properties.Properties()
        set_props.setProperty('pr', 'op', 'test')
        ss = {
            'revision': 'myrev',
            'branch': 'br',
            'project': 'p',
            'repository': 'r',
            'codebase': 'cb',
        }
        idsDeferred, d = sched.trigger(waited_for, sourcestamps=[ss], set_props=set_props)
        self.reactor.advance(0)  # let the debounced function fire

        bsid = yield self.assertTriggeredBuildset(
            idsDeferred,
            waited_for,
            properties={'pr': ('op', 'test')},
            sourcestamps=[
                {
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                    "codebase": 'cb',
                    "revision": 'myrev',
                },
            ],
        )

        # set up a boolean so that we can know when the deferred fires
        self.fired = False

        @d.addCallback
        def fired(xxx_todo_changeme):
            (result, brids) = xxx_todo_changeme
            self.assertEqual(result, 3)  # from sendCompletionMessage
            self.assertEqual(brids, {77: 1})
            self.fired = True

        d.addErrback(log.err)

        # check that the scheduler has subscribed to buildset changes, but
        # not fired yet
        self.assertEqual(
            [q.filter for q in sched.master.mq.qrefs],
            [
                ('schedulers', '13', 'updated'),
                ('buildsets', None, 'complete'),
            ],
        )
        self.assertFalse(self.fired)

        # pretend a non-matching buildset is complete
        self.sendCompletionMessage(27)

        # scheduler should not have reacted
        self.assertEqual(
            [q.filter for q in sched.master.mq.qrefs],
            [
                ('schedulers', '13', 'updated'),
                ('buildsets', None, 'complete'),
            ],
        )
        self.assertFalse(self.fired)

        # pretend the matching buildset is complete
        self.sendCompletionMessage(bsid)
        self.reactor.advance(0)  # let the debounced function fire

        # scheduler should have reacted
        self.assertEqual(
            [q.filter for q in sched.master.mq.qrefs], [('schedulers', '13', 'updated')]
        )
        self.assertTrue(self.fired)
        yield d

    @defer.inlineCallbacks
    def test_trigger_overlapping(self):
        sched = yield self.makeScheduler(codebases={'cb': {'repository': 'r'}})

        # no subscription should be in place yet
        self.assertEqual(sched.master.mq.qrefs, [])

        yield self.master.startService()

        waited_for = False

        def makeSS(rev):
            return {
                'revision': rev,
                'branch': 'br',
                'project': 'p',
                'repository': 'r',
                'codebase': 'cb',
            }

        # trigger the scheduler the first time
        idsDeferred, d = sched.trigger(waited_for, [makeSS('myrev1')])  # triggers bsid 200
        bsid1 = yield self.assertTriggeredBuildset(
            idsDeferred,
            waited_for,
            sourcestamps=[
                {
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                    "codebase": 'cb',
                    "revision": 'myrev1',
                },
            ],
        )
        d.addCallback(
            lambda res_brids: self.assertEqual(res_brids[0], 11)
            and self.assertEqual(res_brids[1], {77: 1})
        )

        waited_for = True
        # and the second time
        idsDeferred, d = sched.trigger(waited_for, [makeSS('myrev2')])  # triggers bsid 201
        self.reactor.advance(0)  # let the debounced function fire
        bsid2 = yield self.assertTriggeredBuildset(
            idsDeferred,
            waited_for,
            sourcestamps=[
                {
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                    "codebase": 'cb',
                    "revision": 'myrev2',
                },
            ],
        )
        d.addCallback(
            lambda res_brids1: self.assertEqual(res_brids1[0], 22)
            and self.assertEqual(res_brids1[1], {77: 2})
        )

        # check that the scheduler has subscribed to buildset changes
        self.assertEqual(
            [q.filter for q in sched.master.mq.qrefs],
            [
                ('schedulers', '13', 'updated'),
                ('buildsets', None, 'complete'),
            ],
        )

        # let a few buildsets complete
        self.sendCompletionMessage(29, results=3)
        self.sendCompletionMessage(bsid2, results=22)
        self.sendCompletionMessage(9, results=3)
        self.sendCompletionMessage(bsid1, results=11)
        self.reactor.advance(0)  # let the debounced function fire

        # both should have triggered with appropriate results, and the
        # subscription should be cancelled
        self.assertEqual(
            [q.filter for q in sched.master.mq.qrefs], [('schedulers', '13', 'updated')]
        )

    @defer.inlineCallbacks
    def test_trigger_with_sourcestamp(self):
        # Test triggering a scheduler with a sourcestamp, and see that
        # sourcestamp handed to addBuildsetForSourceStampsWithDefaults.
        sched = yield self.makeScheduler(overrideBuildsetMethods=True)
        yield self.master.startService()

        waited_for = False
        ss = {
            'repository': 'r3',
            'codebase': 'cb3',
            'revision': 'fixrev3',
            'branch': 'default',
            'project': 'p',
        }
        idsDeferred = sched.trigger(waited_for, sourcestamps=[ss])[0]
        yield idsDeferred

        self.assertEqual(
            self.addBuildsetCalls,
            [
                (
                    'addBuildsetForSourceStampsWithDefaults',
                    {
                        'builderNames': None,
                        'priority': None,
                        'properties': {'scheduler': ('n', 'Scheduler')},
                        'reason': "The Triggerable scheduler named 'n' triggered this build",
                        'sourcestamps': [
                            {
                                'branch': 'default',
                                'codebase': 'cb3',
                                'project': 'p',
                                'repository': 'r3',
                                'revision': 'fixrev3',
                            },
                        ],
                        'waited_for': False,
                    },
                ),
            ],
        )

    @defer.inlineCallbacks
    def test_trigger_without_sourcestamps(self):
        # Test triggering *without* sourcestamps, and see that nothing is passed
        # to addBuildsetForSourceStampsWithDefaults
        waited_for = True
        sched = yield self.makeScheduler(overrideBuildsetMethods=True)
        yield self.master.startService()

        idsDeferred = sched.trigger(waited_for, sourcestamps=[])[0]
        yield idsDeferred

        self.assertEqual(
            self.addBuildsetCalls,
            [
                (
                    'addBuildsetForSourceStampsWithDefaults',
                    {
                        'builderNames': None,
                        'priority': None,
                        'properties': {'scheduler': ('n', 'Scheduler')},
                        'reason': "The Triggerable scheduler named 'n' triggered this build",
                        'sourcestamps': [],
                        'waited_for': True,
                    },
                ),
            ],
        )

    @defer.inlineCallbacks
    def test_trigger_with_reason(self):
        # Test triggering with a reason, and make sure the buildset's reason is updated accordingly
        # (and not the default)
        waited_for = True
        sched = yield self.makeScheduler(overrideBuildsetMethods=True)
        yield self.master.startService()

        set_props = properties.Properties()
        set_props.setProperty('reason', 'test1', 'test')
        idsDeferred, _ = sched.trigger(waited_for, sourcestamps=[], set_props=set_props)
        yield idsDeferred

        self.assertEqual(
            self.addBuildsetCalls,
            [
                (
                    'addBuildsetForSourceStampsWithDefaults',
                    {
                        'builderNames': None,
                        'priority': None,
                        'properties': {
                            'scheduler': ('n', 'Scheduler'),
                            'reason': ('test1', 'test'),
                        },
                        'reason': "test1",
                        'sourcestamps': [],
                        'waited_for': True,
                    },
                ),
            ],
        )

    @defer.inlineCallbacks
    def test_startService_stopService(self):
        yield self.makeScheduler()
        yield self.master.startService()
        yield self.master.stopService()
