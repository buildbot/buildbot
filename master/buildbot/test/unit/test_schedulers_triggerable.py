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
from buildbot.test.fake import fakedb

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
        self.db.insertTestData([
            fakedb.SourceStampSet(id=100),
            fakedb.SourceStamp(id=91, sourcestampsetid=100, revision='myrev', branch='br',
                project='p', repository='r', codebase='cb'),
        ])

        # no subscription should be in place yet
        callbacks = self.master.getSubscriptionCallbacks()
        self.assertEqual(callbacks['buildset_completion'], None)

        # trigger the scheduler, exercising properties while we're at it
        set_props = properties.Properties()
        set_props.setProperty('pr', 'op', 'test')
        d = sched.trigger(100, set_props=set_props)

        bsid = self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[
                         ('pr', ('op', 'test')),
                         ('scheduler', ('n', 'Scheduler')),
                     ],
                     reason='Triggerable(n)',
                     sourcestampsetid=101),
                {'cb':
                 dict(branch='br', project='p', repository='r',
                     codebase='cb', revision='myrev', sourcestampsetid=101)
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
        self.db.insertTestData([
            fakedb.SourceStampSet(id=100),
            fakedb.SourceStampSet(id=101),
            fakedb.SourceStamp(id=91, sourcestampsetid=100, revision='myrev1',
                branch='br', project='p', repository='r', codebase='cb'),
            fakedb.SourceStamp(id=92, sourcestampsetid=101, revision='myrev2',
                branch='br', project='p', repository='r', codebase='cb'),
        ])

        # no subscription should be in place yet
        callbacks = self.master.getSubscriptionCallbacks()
        self.assertEqual(callbacks['buildset_completion'], None)

        # trigger the scheduler the first time
        d = sched.trigger(100)
        bsid1 = self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[('scheduler', ('n', 'Scheduler'))],
                     reason='Triggerable(n)',
                     sourcestampsetid=102),
                {'cb':
                dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev1', sourcestampsetid=102)})
        d.addCallback(lambda (res, brids) : self.assertEqual(res, 11) 
                                        and self.assertEqual(brids, self.db.buildsets.allBuildRequests(bsid1)))

        # and the second time
        d = sched.trigger(101)
        bsid2 = self.db.buildsets.assertBuildset(bsid1+1, # assumes bsid's are sequential
                dict(external_idstring=None,
                     properties=[('scheduler', ('n', 'Scheduler'))],
                     reason='Triggerable(n)', sourcestampsetid=103),
                {'cb':
                dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='myrev2', sourcestampsetid=103)})
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

    def test_trigger_with_fixed_sourcestamps(self):
        # Test a scheduler with 4 repositories. 
        # Trigger the scheduler with a build containing repositories 1 and 2
        # and pass a set of fixed sourcestamps with repositories 1 and 3
        # Expected Result: 
        #    sourcestamp 1 for repository 1 based on fixed sourcestamp
        #    sourcestamp 2 for repository 2 based on sourcestamp from build
        #    sourcestamp 3 for repository 3 based on fixed sourcestamp
        #    sourcestamp 4 for repository 4 based on configured sourcestamp
        sched = self.makeScheduler(
                   codebases = {'cb':{'repository':'r', 'branch': 'branchX'}, 
                                'cb2':{'repository':'r2', 'branch': 'branchX'},
                                'cb3':{'repository':'r3', 'branch': 'branchX'},
                                'cb4':{'repository':'r4', 'branch': 'branchX'},})

        self.db.insertTestData([
            fakedb.SourceStampSet(id=100),
            fakedb.SourceStamp(id=91, sourcestampsetid=100, revision='myrev1',
                branch='br', project='p', repository='r', codebase='cb'),
            fakedb.SourceStamp(id=92, sourcestampsetid=100, revision='myrev2',
                branch='br', project='p', repository='r2', codebase='cb2'),
        ])

        ss1 = {'repository': 'r', 'codebase': 'cb', 'revision': 'fixrev1', 
               'branch': 'default', 'project': 'p' }
        ss2 = {'repository': 'r3', 'codebase': 'cb3', 'revision': 'fixrev3', 
               'branch': 'default', 'project': 'p' }
        d = sched.trigger(100, sourcestamps = [ss1, ss2])

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[('scheduler', ('n', 'Scheduler'))],
                     reason='Triggerable(n)',
                     sourcestampsetid=101),
                {'cb':
                dict(branch='default', project='p', repository='r', codebase='cb',
                     revision='fixrev1', sourcestampsetid=101),
                'cb2':
                dict(branch='br', project='p', repository='r2', codebase='cb2',
                     revision='myrev2', sourcestampsetid=101),
                'cb3':
                dict(branch='default', project='p', repository='r3', codebase='cb3',
                     revision='fixrev3', sourcestampsetid=101),
                'cb4':
                dict(branch='branchX', project='', repository='r4', codebase='cb4',
                     revision=None, sourcestampsetid=101)})

    def test_trigger_with_got_revision(self):
        # Test a scheduler with 2 repositories. 
        # Trigger the scheduler with a build containing repositories 1 and 2
        # and pass a set of got revision values for repository 1 and 2
        # Expected Result: 
        #    sourcestamp 1 for repo 1 based on sourcestamp from build, other revision
        #    sourcestamp 2 for repo 2 based on sourcestamp from build, other revision
        sched = self.makeScheduler(
                codebases = {'cb':{'repository':'r', 'branch': 'branchX'}, 
                             'cb2':{'repository':'r2', 'branch': 'branchX'}})

        self.db.insertTestData([
            fakedb.SourceStampSet(id=100),
            fakedb.SourceStamp(id=91, sourcestampsetid=100, revision='myrev1',
                branch='br', project='p', repository='r', codebase='cb'),
            fakedb.SourceStamp(id=92, sourcestampsetid=100, revision='myrev2',
                branch='br', project='p', repository='r2', codebase='cb2'),
        ])

        got_revision = {'cb': 'gotrevision1a', }
        d = sched.trigger(100, got_revision = got_revision)

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[('scheduler', ('n', 'Scheduler'))],
                     reason='Triggerable(n)',
                     sourcestampsetid=101),
                {'cb':
                dict(branch='br', project='p', repository='r', codebase='cb',
                     revision='gotrevision1a', sourcestampsetid=101),
                'cb2':
                dict(branch='br', project='p', repository='r2', codebase='cb2',
                     revision='myrev2', sourcestampsetid=101),})

    def test_trigger_with_fixed_sourcestamps_and_got_revision(self):
        # Test a scheduler with 3 repositories. 
        # Trigger the scheduler with a build containing repositories 1 and 2
        # and pass a set of got revision values for repository 1 and 2
        # and pass a set of 2 fixed sourcestamps with repository 1 and 3
        # Expected Result: 
        #    sourcestamp 1 for repo 1 based on fixed sourcestamp (ignore got_revision)
        #    sourcestamp 2 for repo 2 based on sourcestamp from build, got revision
        #    sourcestamp 3 for repo 3 based on fixed sourcestamp
        sched = self.makeScheduler(
                codebases = {'cb':{'repository':'r', 'branch': 'branchX'}, 
                             'cb2':{'repository':'r2', 'branch': 'branchX'},
                             'cb3':{'repository':'r3', 'branch': 'branchX'},})

        self.db.insertTestData([
            fakedb.SourceStampSet(id=100),
            fakedb.SourceStamp(id=91, sourcestampsetid=100, revision='myrev1',
                branch='br', project='p', repository='r', codebase='cb'),
            fakedb.SourceStamp(id=92, sourcestampsetid=100, revision='myrev2',
                branch='br', project='p', repository='r2', codebase='cb2'),
        ])

        ss1 = {'repository': 'r', 'codebase': 'cb', 'revision': 'fixrev1', 
               'branch': 'default', 'project': 'p' }
        ss2 = {'repository': 'r3', 'codebase': 'cb3', 'revision': 'fixrev3', 
               'branch': 'default', 'project': 'p' }
        got_revision = {'cb': 'gotrevision1a', 'cb2': 'gotrevision2a', }
        d = sched.trigger(100, sourcestamps = [ss1, ss2], got_revision = got_revision)

        self.db.buildsets.assertBuildset('?',
                dict(external_idstring=None,
                     properties=[('scheduler', ('n', 'Scheduler'))],
                     reason='Triggerable(n)',
                     sourcestampsetid=101),
                {'cb':
                dict(branch='default', project='p', repository='r', codebase='cb',
                     revision='fixrev1', sourcestampsetid=101),
                'cb2':
                dict(branch='br', project='p', repository='r2', codebase='cb2',
                     revision='gotrevision2a', sourcestampsetid=101),
                'cb3':
                dict(branch='default', project='p', repository='r3', codebase='cb3',
                     revision='fixrev3', sourcestampsetid=101),})
