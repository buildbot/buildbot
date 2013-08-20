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

import mock
from twisted.internet import defer, task
from twisted.python import log
from twisted.trial import unittest
from buildbot.schedulers import triggerable
from buildbot.process import properties
from buildbot.test.util import interfaces, scheduler

class TriggerableInterface(unittest.TestCase, interfaces.InterfaceTests):
    def test_interface(self):
        self.assertInterfacesImplemented(triggerable.Triggerable)

class Triggerable(scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 33

    def setUp(self):
        # Necessary to get an assertable submitted_at time.
        self.now = 946684799
        self.clock = task.Clock()
        self.clock.advance(self.now)
        self.clock_patch = mock.patch('buildbot.test.fake.fakedb.reactor.seconds', self.clock.seconds)
        self.clock_patch.start()

        self.setUpScheduler()
        self.subscription = None

    def tearDown(self):
        self.tearDownScheduler()
        self.clock_patch.stop()

    def makeScheduler(self, **kwargs):
        sched = self.attachScheduler(
                triggerable.Triggerable(name='n', builderNames=['b'], **kwargs),
                self.OBJECTID)

        return sched

    @defer.inlineCallbacks
    def assertTriggeredBuildset(self, idsDeferred, waited_for, properties={}, sourcestamps=None):
        bsid, brids = yield idsDeferred
        properties.update({ u'scheduler' : ( 'n', u'Scheduler') })

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
                'reason': u'Triggerable(n)',
                'results': -1,
                #'sourcestamps': [100],
                'submitted_at': datetime(1999, 12, 31, 23, 59, 59, tzinfo=UTC),
            }
        )
        
        
        actual_sourcestamps = yield defer.gatherResults([
            self.master.db.sourcestamps.getSourceStamp(ssid)
            for ssid in ssids
        ])

        self.assertEqual(len(sourcestamps), len(actual_sourcestamps))
        for expected_ss, actual_ss in zip(sourcestamps, actual_sourcestamps):
            actual_ss = actual_ss.copy()
            # We don't care if the actual sourcestamp has *more* attributes than expected.
            for key in actual_ss.keys():
                if key not in expected_ss:
                    del actual_ss[key]
            self.assertEqual(expected_ss, actual_ss)
            

        for brid in brids.values():
            #from datetime import datetime
            #from buildbot.util import UTC
            buildrequest = yield self.master.db.buildrequests.getBuildRequest(brid)
            self.assertEqual(
                buildrequest,
                {
                    'brid': brid,
                    'buildername': u'b',
                    'buildsetid': bsid,
                    'claimed': False,
                    'claimed_at': None,
                    'complete': False,
                    'complete_at': None,
                    'mine': False,
                    'priority': 0,
                    'results': -1,
                    'submitted_at': None,
                    'waited_for': waited_for,
                }
            )
            

    def sendCompletionMessage(self, bsid, results=3):
        self.master.mq.callConsumer(('buildset', str(bsid), 'complete'),
            dict(
                bsid=bsid,
                submitted_at=100,
                complete=True,
                complete_at=200,
                external_idstring=None,
                reason=u'triggering',
                results=results,
                sourcestamps=[],
                ))

    # tests

    # NOTE: these tests take advantage of the fact that all of the fake
    # scheduler operations are synchronous, and thus do not return a Deferred.
    # The Deferred from trigger() is completely processed before this test
    # method returns.

    def test_trigger(self):
        sched = self.makeScheduler(codebases = {'cb':{'repository':'r'}})
        # no subscription should be in place yet
        self.assertEqual(sched.master.mq.qrefs, [])

        # trigger the scheduler, exercising properties while we're at it
        waited_for = True
        set_props = properties.Properties()
        set_props.setProperty('pr', 'op', 'test')
        ss = {'revision':'myrev',
              'branch':'br',
              'project':'p',
              'repository':'r',
              'codebase':'cb' }
        idsDeferred, d = sched.trigger(waited_for, sourcestamps=[ss], set_props=set_props)

        self.assertTriggeredBuildset(
            idsDeferred,
            waited_for,
            properties={ u'pr': ('op', u'test') },
            sourcestamps=[
                 dict(branch='br', project='p', repository='r',
                     codebase='cb', revision='myrev'),
            ])

        # set up a boolean so that we can know when the deferred fires
        self.fired = False
        def fired((result, brids)):
            self.assertEqual(result, 3) # from sendCompletionMessage
            self.assertEqual(brids, {u'b':1000})
            self.fired = True
        d.addCallback(fired)
        d.addErrback(log.err)

        # check that the scheduler has subscribed to buildset changes, but
        # not fired yet
        self.assertEqual(
            [ q.filter for q in sched.master.mq.qrefs ],
            [('buildset', None, 'complete',)])
        self.assertFalse(self.fired)

        # pretend a non-matching buildset is complete
        self.sendCompletionMessage(27)

        # scheduler should not have reacted
        self.assertEqual(
            [ q.filter for q in sched.master.mq.qrefs ],
            [('buildset', None, 'complete',)])
        self.assertFalse(self.fired)

        # pretend the matching buildset is complete
        self.sendCompletionMessage(200)

        # scheduler should have reacted
        self.assertEqual(
            [ q.filter for q in sched.master.mq.qrefs ],
            [])
        self.assertTrue(self.fired)
        return d

    def test_trigger_overlapping(self):
        sched = self.makeScheduler(codebases = {'cb':{'repository':'r'}})

        # no subscription should be in place yet
        self.assertEqual(sched.master.mq.qrefs, [])

        waited_for = False
        def makeSS(rev):
            return { 'revision':rev, 'branch':'br', 'project':'p',
                     'repository':'r', 'codebase':'cb' }

        # trigger the scheduler the first time
        idsDeferred, d = sched.trigger(waited_for, [makeSS('myrev1')]) # triggers bsid 200
        self.assertTriggeredBuildset(
            idsDeferred,
            waited_for,
            sourcestamps=[
                 dict(branch='br', project='p', repository='r',
                     codebase='cb', revision='myrev1'),
                ])
        d.addCallback(lambda (res, brids) : self.assertEqual(res, 11)
                and self.assertEqual(brids, {u'b':1000}))

        waited_for = True
        # and the second time
        idsDeferred, d = sched.trigger(waited_for, [makeSS('myrev2')]) # triggers bsid 201
        self.assertTriggeredBuildset(
            idsDeferred,
            waited_for,
            sourcestamps=[
                 dict(branch='br', project='p', repository='r',
                     codebase='cb', revision='myrev2'),
                ])
        d.addCallback(lambda (res, brids) : self.assertEqual(res, 22) 
                and self.assertEqual(brids, {u'b':1001}))

        # check that the scheduler has subscribed to buildset changes
        self.assertEqual(
            [ q.filter for q in sched.master.mq.qrefs ],
            [('buildset', None, 'complete',)])

        # let a few buildsets complete
        self.sendCompletionMessage(29, results=3)
        self.sendCompletionMessage(201, results=22)
        self.sendCompletionMessage(9, results=3)
        self.sendCompletionMessage(200, results=11)

        # both should have triggered with appropriate results, and the
        # subscription should be cancelled
        self.assertEqual(sched.master.mq.qrefs, [])

    def test_trigger_with_sourcestamp(self):
        # Test a scheduler with 2 repositories.
        # Trigger the scheduler with a sourcestamp that is unknown to the scheduler
        # Expected Result: 
        #    sourcestamp 1 for repository 1 based on configured sourcestamp
        #    sourcestamp 2 for repository 2 based on configured sourcestamp
        sched = self.makeScheduler()

        waited_for = False
        ss = {'repository': 'r3', 'codebase': 'cb3', 'revision': 'fixrev3',
               'branch': 'default', 'project': 'p' }
        idsDeferred = sched.trigger(waited_for, sourcestamps=[ss])[0]

        self.assertTriggeredBuildset(idsDeferred, waited_for, sourcestamps=[ss])

    def test_trigger_without_sourcestamps(self):
        # Test a scheduler with 2 repositories.
        # Trigger the scheduler without a sourcestamp; this should translate to
        # a call to addBuildsetForSourceStampsWithDefaults with no sourcestamps
        waited_for = True
        sched = self.makeScheduler()
        idsDeferred = sched.trigger(waited_for, sourcestamps=[])[0]
        self.assertTriggeredBuildset(idsDeferred, waited_for, sourcestamps=[])
