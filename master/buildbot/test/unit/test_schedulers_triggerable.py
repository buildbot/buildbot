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

from twisted.trial import unittest
from buildbot.schedulers import triggerable
from buildbot.process import properties
from buildbot.test.util import scheduler

class Triggerable(scheduler.SchedulerMixin, unittest.TestCase):

    SCHEDULERID = 33

    def setUp(self):
        self.setUpScheduler()
        self.subscription = None

    def tearDown(self):
        self.tearDownScheduler()

    def makeScheduler(self, **kwargs):
        sched = self.attachScheduler(
                triggerable.Triggerable(name='n', builderNames=['b']),
                self.SCHEDULERID)

        return sched

    # tests

    # NOTE: these tests take advantage of the fact that all of the fake
    # scheduler operations are synchronous, and thus do not return a Deferred.
    # The Deferred from trigger() is completely processed before this test
    # method returns.

    def test_trigger(self):
        sched = self.makeScheduler()

        # no subscription should be in place yet
        callbacks = self.master.getSubscriptionCallbacks()
        self.assertEqual(callbacks['buildset_completion'], None)

        # trigger the scheduler, exercising properties while we're at it
        ssid = self.db.sourcestamps.fakeSourceStamp(rev='myrev')
        set_props = properties.Properties()
        set_props.setProperty('pr', 'op', 'test')
        d = sched.trigger(ssid, set_props=set_props)

        # set up a boolean so that we can know when the deferred fires
        self.fired = False
        def fired(result):
            self.assertEqual(result, 13) # 13 comes from the result below
            self.fired = True
        d.addCallback(fired)

        bsid = self.db.buildsets.assertBuildset('?',
                dict(builderNames=['b'],
                     external_idstring=None,
                     properties=[
                         ('pr', ('op', 'test')),
                         ('scheduler', ('n', 'Scheduler')),
                     ],
                     reason='Triggerable(n)'),
                dict(rev='myrev'))

        # check that the scheduler has subscribed to buildset changes, but
        # not fired yet
        callbacks = self.master.getSubscriptionCallbacks()
        self.assertNotEqual(callbacks['buildset_completion'], None)
        self.assertFalse(self.fired)

        # pretend a non-matching buildset is complete
        callbacks['buildset_completion'](bsid+27, 3)

        # scheduler should not have reacted
        callbacks = self.master.getSubscriptionCallbacks()
        self.assertNotEqual(callbacks['buildset_completion'], None)
        self.assertFalse(self.fired)

        # pretend the matching buildset is complete
        callbacks['buildset_completion'](bsid, 13)

        # scheduler should have reacted
        callbacks = self.master.getSubscriptionCallbacks()
        self.assertEqual(callbacks['buildset_completion'], None)
        self.assertTrue(self.fired)

    def test_trigger_overlapping(self):
        sched = self.makeScheduler()

        # no subscription should be in place yet
        callbacks = self.master.getSubscriptionCallbacks()
        self.assertEqual(callbacks['buildset_completion'], None)

        # trigger the scheduler the first time
        ssid1 = self.db.sourcestamps.fakeSourceStamp(rev='trig1')
        d = sched.trigger(ssid1)
        d.addCallback(lambda res : self.assertEqual(res, 11))
        bsid1 = self.db.buildsets.assertBuildset('?',
                dict(builderNames=['b'],
                     external_idstring=None,
                     properties=[('scheduler', ('n', 'Scheduler'))],
                     reason='Triggerable(n)'),
                dict(rev='trig1'))

        # and the second time
        ssid2 = self.db.sourcestamps.fakeSourceStamp(rev='trig2')
        d = sched.trigger(ssid2)
        d.addCallback(lambda res : self.assertEqual(res, 22))
        bsid2 = self.db.buildsets.assertBuildset(bsid1+1, # assumes bsid's are sequential
                dict(builderNames=['b'],
                     external_idstring=None,
                     properties=[('scheduler', ('n', 'Scheduler'))],
                     reason='Triggerable(n)'),
                dict(rev='trig2'))

        # check that the scheduler has subscribed to buildset changes
        callbacks = self.master.getSubscriptionCallbacks()
        self.assertNotEqual(callbacks['buildset_completion'], None)

        # let a few buildsets complete
        callbacks['buildset_completion'](bsid2+27, 3)
        callbacks['buildset_completion'](bsid2, 22)
        callbacks['buildset_completion'](bsid2+7, 3)
        callbacks['buildset_completion'](bsid1, 11)

        # both should have triggered with appropriate results, and the
        # subscription should be cancelled
        callbacks = self.master.getSubscriptionCallbacks()
        self.assertEqual(callbacks['buildset_completion'], None)
