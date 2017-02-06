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
from future.utils import itervalues

import mock

from twisted.internet import defer
from twisted.internet import task
from twisted.python import log
from twisted.trial import unittest

from buildbot.process import properties
from buildbot.schedulers import triggerable
from buildbot.test.fake import fakedb
from buildbot.test.util import interfaces
from buildbot.test.util import scheduler


class TriggerableInterfaceTest(unittest.TestCase, interfaces.InterfaceTests):

    def test_interface(self):
        self.assertInterfacesImplemented(triggerable.Triggerable)


class Triggerable(scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 33
    SCHEDULERID = 13

    def setUp(self):
        # Necessary to get an assertable submitted_at time.
        self.now = 946684799
        self.clock = task.Clock()
        self.clock.advance(self.now)
        self.clock_patch = mock.patch(
            'buildbot.test.fake.fakedb.reactor.seconds', self.clock.seconds)
        self.clock_patch.start()

        self.setUpScheduler()
        # Patch reactor for sched._updateWaiters debounce
        self.master.reactor = self.clock
        self.subscription = None

    def tearDown(self):
        self.tearDownScheduler()
        self.clock_patch.stop()

    def makeScheduler(self, overrideBuildsetMethods=False, **kwargs):
        self.master.db.insertTestData([fakedb.Builder(id=77, name='b')])

        sched = self.attachScheduler(
            triggerable.Triggerable(name='n', builderNames=['b'], **kwargs),
            self.OBJECTID, self.SCHEDULERID,
            overrideBuildsetMethods=overrideBuildsetMethods)

        return sched

    @defer.inlineCallbacks
    def assertTriggeredBuildset(self, idsDeferred, waited_for, properties={}, sourcestamps=None):
        bsid, brids = yield idsDeferred
        properties.update({u'scheduler': ('n', u'Scheduler')})

        self.assertEqual(
            self.master.db.buildsets.buildsets[bsid]['properties'],
            properties,
        )

        buildset = yield self.master.db.buildsets.getBuildset(bsid)

        from datetime import datetime
        from buildbot.util import UTC
        ssids = buildset.pop('sourcestamps')

        self.assertEqual(
            buildset,
            {
                'bsid': bsid,
                'complete': False,
                'complete_at': None,
                'external_idstring': None,
                'reason': u"The Triggerable scheduler named 'n' triggered this build",
                'results': -1,
                'submitted_at': datetime(1999, 12, 31, 23, 59, 59, tzinfo=UTC),
                'parent_buildid': None,
                'parent_relationship': None,
            }
        )

        actual_sourcestamps = yield defer.gatherResults([
            self.master.db.sourcestamps.getSourceStamp(ssid)
            for ssid in ssids
        ])

        self.assertEqual(len(sourcestamps), len(actual_sourcestamps))
        for expected_ss, actual_ss in zip(sourcestamps, actual_sourcestamps):
            actual_ss = actual_ss.copy()
            # We don't care if the actual sourcestamp has *more* attributes
            # than expected.
            for key in list(actual_ss.keys()):
                if key not in expected_ss:
                    del actual_ss[key]
            self.assertEqual(expected_ss, actual_ss)

        for brid in itervalues(brids):
            buildrequest = yield self.master.db.buildrequests.getBuildRequest(brid)
            self.assertEqual(
                buildrequest,
                {
                    'buildrequestid': brid,
                    'buildername': u'b',
                    'builderid': 77,
                    'buildsetid': bsid,
                    'claimed': False,
                    'claimed_at': None,
                    'complete': False,
                    'complete_at': None,
                    'claimed_by_masterid': None,
                    'priority': 0,
                    'results': -1,
                    'submitted_at': datetime(1999, 12, 31, 23, 59, 59, tzinfo=UTC),
                    'waited_for': waited_for
                }
            )

    def sendCompletionMessage(self, bsid, results=3):
        self.master.mq.callConsumer(('buildsets', str(bsid), 'complete'),
                                    dict(
                                        bsid=bsid,
                                        submitted_at=100,
                                        complete=True,
                                        complete_at=200,
                                        external_idstring=None,
                                        reason=u'triggering',
                                        results=results,
                                        sourcestamps=[],
                                        parent_buildid=None,
                                        parent_relationship=None,
        ))

    # tests

    # NOTE: these tests take advantage of the fact that all of the fake
    # scheduler operations are synchronous, and thus do not return a Deferred.
    # The Deferred from trigger() is completely processed before this test
    # method returns.

    def test_constructor_no_reason(self):
        sched = self.makeScheduler()
        self.assertEqual(
            sched.reason, None)  # default reason is dynamic

    def test_constructor_explicit_reason(self):
        sched = self.makeScheduler(reason="Because I said so")
        self.assertEqual(sched.reason, "Because I said so")

    def test_trigger(self):
        sched = self.makeScheduler(codebases={'cb': {'repository': 'r'}})
        # no subscription should be in place yet
        self.assertEqual(sched.master.mq.qrefs, [])

        # trigger the scheduler, exercising properties while we're at it
        waited_for = True
        set_props = properties.Properties()
        set_props.setProperty('pr', 'op', 'test')
        ss = {'revision': 'myrev',
              'branch': 'br',
              'project': 'p',
              'repository': 'r',
              'codebase': 'cb'}
        idsDeferred, d = sched.trigger(
            waited_for, sourcestamps=[ss], set_props=set_props)
        self.clock.advance(0)  # let the debounced function fire

        self.assertTriggeredBuildset(
            idsDeferred,
            waited_for,
            properties={u'pr': ('op', u'test')},
            sourcestamps=[
                dict(branch='br', project='p', repository='r',
                     codebase='cb', revision='myrev'),
            ])

        # set up a boolean so that we can know when the deferred fires
        self.fired = False

        @d.addCallback
        def fired(xxx_todo_changeme):
            (result, brids) = xxx_todo_changeme
            self.assertEqual(result, 3)  # from sendCompletionMessage
            self.assertEqual(brids, {77: 1000})
            self.fired = True
        d.addErrback(log.err)

        # check that the scheduler has subscribed to buildset changes, but
        # not fired yet
        self.assertEqual(
            [q.filter for q in sched.master.mq.qrefs],
            [('buildsets', None, 'complete',)])
        self.assertFalse(self.fired)

        # pretend a non-matching buildset is complete
        self.sendCompletionMessage(27)

        # scheduler should not have reacted
        self.assertEqual(
            [q.filter for q in sched.master.mq.qrefs],
            [('buildsets', None, 'complete',)])
        self.assertFalse(self.fired)

        # pretend the matching buildset is complete
        self.sendCompletionMessage(200)
        self.clock.advance(0)  # let the debounced function fire

        # scheduler should have reacted
        self.assertEqual(
            [q.filter for q in sched.master.mq.qrefs],
            [])
        self.assertTrue(self.fired)
        return d

    def test_trigger_overlapping(self):
        sched = self.makeScheduler(codebases={'cb': {'repository': 'r'}})

        # no subscription should be in place yet
        self.assertEqual(sched.master.mq.qrefs, [])

        waited_for = False

        def makeSS(rev):
            return {'revision': rev, 'branch': 'br', 'project': 'p',
                    'repository': 'r', 'codebase': 'cb'}

        # trigger the scheduler the first time
        idsDeferred, d = sched.trigger(
            waited_for, [makeSS('myrev1')])  # triggers bsid 200
        self.assertTriggeredBuildset(
            idsDeferred,
            waited_for,
            sourcestamps=[
                dict(branch='br', project='p', repository='r',
                     codebase='cb', revision='myrev1'),
            ])
        d.addCallback(lambda res_brids: self.assertEqual(res_brids[0], 11)
                      and self.assertEqual(res_brids[1], {77: 1000}))

        waited_for = True
        # and the second time
        idsDeferred, d = sched.trigger(
            waited_for, [makeSS('myrev2')])  # triggers bsid 201
        self.clock.advance(0)  # let the debounced function fire
        self.assertTriggeredBuildset(
            idsDeferred,
            waited_for,
            sourcestamps=[
                dict(branch='br', project='p', repository='r',
                     codebase='cb', revision='myrev2'),
            ])
        d.addCallback(lambda res_brids1: self.assertEqual(res_brids1[0], 22)
                      and self.assertEqual(res_brids1[1], {77: 1001}))

        # check that the scheduler has subscribed to buildset changes
        self.assertEqual(
            [q.filter for q in sched.master.mq.qrefs],
            [('buildsets', None, 'complete',)])

        # let a few buildsets complete
        self.sendCompletionMessage(29, results=3)
        self.sendCompletionMessage(201, results=22)
        self.sendCompletionMessage(9, results=3)
        self.sendCompletionMessage(200, results=11)
        self.clock.advance(0)  # let the debounced function fire

        # both should have triggered with appropriate results, and the
        # subscription should be cancelled
        self.assertEqual(sched.master.mq.qrefs, [])

    @defer.inlineCallbacks
    def test_trigger_with_sourcestamp(self):
        # Test triggering a scheduler with a sourcestamp, and see that
        # sourcestamp handed to addBuildsetForSourceStampsWithDefaults.
        sched = self.makeScheduler(overrideBuildsetMethods=True)

        waited_for = False
        ss = {'repository': 'r3', 'codebase': 'cb3', 'revision': 'fixrev3',
              'branch': 'default', 'project': 'p'}
        idsDeferred = sched.trigger(waited_for, sourcestamps=[ss])[0]
        yield idsDeferred

        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', {
                'builderNames': None,
                'properties': {'scheduler': ('n', 'Scheduler')},
                'reason': "The Triggerable scheduler named 'n' triggered "
                          "this build",
                'sourcestamps': [{
                    'branch': 'default',
                    'codebase': 'cb3',
                    'project': 'p',
                    'repository': 'r3',
                    'revision': 'fixrev3'},
                ],
                'waited_for': False}),
        ])

    @defer.inlineCallbacks
    def test_trigger_without_sourcestamps(self):
        # Test triggering *without* sourcestamps, and see that nothing is passed
        # to addBuildsetForSourceStampsWithDefaults
        waited_for = True
        sched = self.makeScheduler(overrideBuildsetMethods=True)
        idsDeferred = sched.trigger(waited_for, sourcestamps=[])[0]
        yield idsDeferred

        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', {
                'builderNames': None,
                'properties': {'scheduler': ('n', 'Scheduler')},
                'reason': "The Triggerable scheduler named 'n' triggered "
                          "this build",
                'sourcestamps': [],
                'waited_for': True}),
        ])

    @defer.inlineCallbacks
    def test_trigger_with_reason(self):
        # Test triggering with a reason, and make sure the buildset's reason is updated accordingly
        # (and not the default)
        waited_for = True
        sched = self.makeScheduler(overrideBuildsetMethods=True)
        set_props = properties.Properties()
        set_props.setProperty('reason', 'test1', 'test')
        idsDeferred, d = sched.trigger(
            waited_for, sourcestamps=[], set_props=set_props)
        yield idsDeferred

        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', {
                'builderNames': None,
                'properties': {'scheduler': ('n', 'Scheduler'), 'reason': ('test1', 'test')},
                'reason': "test1",
                'sourcestamps': [],
                'waited_for': True}),
        ])

    @defer.inlineCallbacks
    def test_startService_stopService(self):
        sched = self.makeScheduler()
        yield sched.startService()
        yield sched.stopService()
