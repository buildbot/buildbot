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

from twisted.python import log
from twisted.trial import unittest
from buildbot.schedulers import triggerable
from buildbot.process import properties
from buildbot.test.util import scheduler

class Triggerable(scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 33

    def setUp(self):
        self.setUpScheduler()
        self.subscription = None

    def tearDown(self):
        self.tearDownScheduler()

    def makeScheduler(self, **kwargs):
        sched = self.attachScheduler(
                triggerable.Triggerable(name='n', builderNames=['b'], **kwargs),
                self.OBJECTID, overrideBuildsetMethods=True)

        return sched

    def assertTriggeredBuildset(self, properties={}, sourcestamps=None):
        properties.update({ u'scheduler' : ( 'n', u'Scheduler') })
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', dict(
                builderNames=None, # uses the default
                properties=properties,
                reason=u'Triggerable(n)',
                sourcestamps=sourcestamps)),
        ])
        self.addBuildsetCalls = []

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
        set_props = properties.Properties()
        set_props.setProperty('pr', 'op', 'test')
        ss = {'revision':'myrev',
              'branch':'br',
              'project':'p',
              'repository':'r',
              'codebase':'cb' }
        d = sched.trigger([ss], set_props=set_props)

        self.assertTriggeredBuildset(
            properties={ u'pr': ('op', u'test') },
            sourcestamps=[
                 dict(branch='br', project='p', repository='r',
                     codebase='cb', revision='myrev'),
            ])

        # set up a boolean so that we can know when the deferred fires
        self.fired = False
        def fired((result, brids)):
            self.assertEqual(result, 3) # from sendCompletionMessage
            self.assertEqual(brids, {u'b':100})
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
        self.sendCompletionMessage(500)

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

        def makeSS(rev):
            return { 'revision':rev, 'branch':'br', 'project':'p',
                     'repository':'r', 'codebase':'cb' }

        # trigger the scheduler the first time
        d = sched.trigger([makeSS('myrev1')]) # triggers bsid 500
        self.assertTriggeredBuildset(
            sourcestamps=[
                 dict(branch='br', project='p', repository='r',
                     codebase='cb', revision='myrev1'),
                ])
        d.addCallback(lambda (res, brids) : self.assertEqual(res, 11)
                and self.assertEqual(brids, {u'b':100}))

        # and the second time
        d = sched.trigger([makeSS('myrev2')]) # triggers bsid 501
        self.assertTriggeredBuildset(
            sourcestamps=[
                 dict(branch='br', project='p', repository='r',
                     codebase='cb', revision='myrev2'),
                ])
        d.addCallback(lambda (res, brids) : self.assertEqual(res, 22) 
                and self.assertEqual(brids, {u'b':101}))

        # check that the scheduler has subscribed to buildset changes
        self.assertEqual(
            [ q.filter for q in sched.master.mq.qrefs ],
            [('buildset', None, 'complete',)])

        # let a few buildsets complete
        self.sendCompletionMessage(29, results=3)
        self.sendCompletionMessage(501, results=22)
        self.sendCompletionMessage(9, results=3)
        self.sendCompletionMessage(500, results=11)

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

        ss = {'repository': 'r3', 'codebase': 'cb3', 'revision': 'fixrev3',
               'branch': 'default', 'project': 'p' }
        sched.trigger(sourcestamps=[ss])

        self.assertTriggeredBuildset(sourcestamps=[ss])

    def test_trigger_without_sourcestamps(self):
        # Test a scheduler with 2 repositories.
        # Trigger the scheduler without a sourcestamp; this should translate to
        # a call to addBuildsetForSourceStampsWithDefaults with no sourcestamps
        sched = self.makeScheduler()
        sched.trigger(sourcestamps=[])
        self.assertTriggeredBuildset(sourcestamps=[])
