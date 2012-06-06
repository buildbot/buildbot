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

    OBJECTID = 33

    def setUp(self):
        self.setUpScheduler()
        self.subscription = None

    def tearDown(self):
        self.tearDownScheduler()

    def makeScheduler(self, **kwargs):
        sched = self.attachScheduler(
                triggerable.Triggerable(name='n', builderNames=['b'], **kwargs),
                self.OBJECTID)

        return sched

    # tests

    # NOTE: these tests take advantage of the fact that all of the fake
    # scheduler operations are synchronous, and thus do not return a Deferred.
    # The Deferred from trigger() is completely processed before this test
    # method returns.

    def test_trigger(self):
        sched = self.makeScheduler(codebases = {'cb':{'repository':'r'}})
        # no subscription should be in place yet
        callbacks = self.master.getSubscriptionCallbacks()
        self.assertEqual(callbacks['buildset_completion'], None)

        # trigger the scheduler, exercising properties while we're at it
        set_props = properties.Properties()
        set_props.setProperty('pr', 'op', 'test')
        ss = {'revision':'myrev',
              'branch':'br',
              'project':'p',
              'repository':'r',
              'codebase':'cb' }
        d = sched.trigger({'cb': ss}, set_props=set_props)

        bsid = self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('pr', ('op', 'test')),
                         ('scheduler', ('n', 'Scheduler')),
                     ],
                     reason='Triggerable(n)',
                     sourcestampsetid=100),
                {'cb':
                 dict(branch='br', project='p', repository='r',
                     codebase='cb', revision='myrev', sourcestampsetid=100)
                })
        # set up a boolean so that we can know when the deferred fires
        self.fired = False
        def fired((result, brids)):
            self.assertEqual(result, 13) # 13 comes from the result below
            self.assertEqual(brids, self.db.buildsets.allBuildRequests(bsid))
            self.fired = True
        d.addCallback(fired)

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
        sched = self.makeScheduler(codebases = {'cb':{'repository':'r'}})

        # no subscription should be in place yet
        callbacks = self.master.getSubscriptionCallbacks()
        self.assertEqual(callbacks['buildset_completion'], None)

        # define sourcestamp
        ss = {'revision':'myrev1',
          'branch':'br',
          'project':'p',
          'repository':'r',
          'codebase':'cb' }
        # trigger the scheduler the first time
        d = sched.trigger({'cb':ss})
        bsid1 = self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[('scheduler', ('n', 'Scheduler'))],
                     reason='Triggerable(n)',
                     sourcestampsetid=100),
                {'cb':
                dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev1', sourcestampsetid=100)})
        d.addCallback(lambda (res, brids) : self.assertEqual(res, 11) 
                                        and self.assertEqual(brids, self.db.buildsets.allBuildRequests(bsid1)))

        # define sourcestamp
        ss = {'revision':'myrev2',
          'branch':'br',
          'project':'p',
          'repository':'r',
          'codebase':'cb' }
        # and the second time
        d = sched.trigger({'cb':ss})
        bsid2 = self.db.buildsets.assertBuildset(bsid1+1, # assumes bsid's are sequential
                dict(external_idstring=None,
                     properties=[('scheduler', ('n', 'Scheduler'))],
                     reason='Triggerable(n)', sourcestampsetid=101),
                {'cb':
                dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev2', sourcestampsetid=101)})
        d.addCallback(lambda (res, brids) : self.assertEqual(res, 22) 
                                        and self.assertEqual(brids, self.db.buildsets.allBuildRequests(bsid2)))

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

    def test_trigger_with_unknown_sourcestamp(self):
        # Test a scheduler with 2 repositories.
        # Trigger the scheduler with a sourcestamp that is unknown to the scheduler
        # Expected Result: 
        #    sourcestamp 1 for repository 1 based on configured sourcestamp
        #    sourcestamp 2 for repository 2 based on configured sourcestamp
        sched = self.makeScheduler(
                   codebases = {'cb':{'repository':'r', 'branch': 'branchX'},
                                'cb2':{'repository':'r2', 'branch': 'branchX'},})

        ss = {'repository': 'r3', 'codebase': 'cb3', 'revision': 'fixrev3',
               'branch': 'default', 'project': 'p' }
        sched.trigger(sourcestamps = {'cb3': ss})

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[('scheduler', ('n', 'Scheduler'))],
                     reason='Triggerable(n)',
                     sourcestampsetid=100),
                {'cb':
                dict(branch='branchX', project='', repository='r', codebase='cb',
                     revision=None, sourcestampsetid=100),
                'cb2':
                dict(branch='branchX', project='', repository='r2', codebase='cb2',
                     revision=None, sourcestampsetid=100),})

    def test_trigger_without_sourcestamps(self):
        # Test a scheduler with 2 repositories.
        # Trigger the scheduler without a sourcestamp
        # Expected Result: 
        #    sourcestamp 1 for repository 1 based on configured sourcestamp
        #    sourcestamp 2 for repository 2 based on configured sourcestamp
        sched = self.makeScheduler(
                   codebases = {'cb':{'repository':'r', 'branch': 'branchX'},
                                'cb2':{'repository':'r2', 'branch': 'branchX'},})

        sched.trigger(sourcestamps = None)

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[('scheduler', ('n', 'Scheduler'))],
                     reason='Triggerable(n)',
                     sourcestampsetid=100),
                {'cb':
                dict(branch='branchX', project='', repository='r', codebase='cb',
                     revision=None, sourcestampsetid=100),
                'cb2':
                dict(branch='branchX', project='', repository='r2', codebase='cb2',
                     revision=None, sourcestampsetid=100),})