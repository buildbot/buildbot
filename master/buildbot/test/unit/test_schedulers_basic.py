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
from twisted.trial import unittest
from twisted.internet import defer, task
from buildbot import config
from buildbot.test.fake import fakedb
from buildbot.schedulers import basic
from buildbot.test.util import scheduler

class CommonStuffMixin(object):

    def makeScheduler(self, klass, **kwargs_override):
        kwargs = dict(name="tsched", treeStableTimer=60,
                      builderNames=['tbuild'])
        kwargs.update(kwargs_override)
        sched = self.attachScheduler(klass(**kwargs), self.OBJECTID)

        # add a Clock to help checking timing issues
        self.clock = sched._reactor = task.Clock()

        # keep track of builds in self.events
        self.events = []
        def addBuildsetForChanges(reason='', external_idstring=None, changeids=[]):
            self.assertEqual(external_idstring, None)
            self.assertEqual(reason, 'scheduler') # basic schedulers all use this
            self.events.append('B%s@%d' % (`changeids`.replace(' ',''),
                                           self.clock.seconds()))
            return defer.succeed(None)
        sched.addBuildsetForChanges = addBuildsetForChanges

        # see self.assertConsumingChanges
        self.consumingChanges = None
        def startConsumingChanges(**kwargs):
            self.consumingChanges = kwargs
            return defer.succeed(None)
        sched.startConsumingChanges = startConsumingChanges

        return sched

    def assertConsumingChanges(self, **kwargs):
        self.assertEqual(self.consumingChanges, kwargs)

class BaseBasicScheduler(CommonStuffMixin,
        scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 244

    # a custom subclass since we're testing the base class.  This basically
    # re-implements SingleBranchScheduler, but with more asserts
    class Subclass(basic.BaseBasicScheduler):
        timer_started = False
        def getChangeFilter(self, *args, **kwargs):
            return kwargs.get('change_filter')

        def getTimerNameForChange(self, change):
            self.timer_started = True
            return "xxx"

        def getChangeClassificationsForTimer(self, objectid, timer_name):
            assert timer_name == "xxx"
            assert objectid == BaseBasicScheduler.OBJECTID
            return self.master.db.schedulers.getChangeClassifications(objectid)

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    # tests

    def test_constructor_positional_exception(self):
        self.assertRaises(config.ConfigErrors,
                lambda : self.Subclass("tsched", "master", 60))

    def test_startService_no_treeStableTimer(self):
        cf = mock.Mock('cf')
        fII = mock.Mock('fII')
        sched = self.makeScheduler(self.Subclass, treeStableTimer=None, change_filter=cf,
                                   fileIsImportant=fII)

        self.db.schedulers.fakeClassifications(self.OBJECTID, { 20 : True })

        d = sched.startService(_returnDeferred=True)

        # check that the scheduler has started to consume changes, and the
        # classifications *have* been flushed, since they will not be used
        def check(_):
            self.assertConsumingChanges(fileIsImportant=fII, change_filter=cf,
                                        onlyImportant=False)
            self.db.schedulers.assertClassifications(self.OBJECTID, {})
        d.addCallback(check)
        d.addCallback(lambda _ : sched.stopService())
        return d

    def test_subclass_fileIsImportant(self):
        class Subclass(self.Subclass):
            def fileIsImportant(self, change):
                return False
        sched = self.makeScheduler(Subclass, onlyImportant=True)
        self.failUnlessEqual(Subclass.fileIsImportant.__get__(sched), sched.fileIsImportant)

    def test_startService_treeStableTimer(self):
        cf = mock.Mock()
        sched = self.makeScheduler(self.Subclass, treeStableTimer=10, change_filter=cf)

        self.db.schedulers.fakeClassifications(self.OBJECTID, { 20 : True })
        self.master.db.insertTestData([
            fakedb.Change(changeid=20),
            fakedb.SchedulerChange(objectid=self.OBJECTID,
                                                changeid=20, important=1)
        ])

        d = sched.startService(_returnDeferred=True)

        # check that the scheduler has started to consume changes, and no
        # classifications have been flushed.  Furthermore, the existing
        # classification should have been acted on, so the timer should be
        # running
        def check(_):
            self.assertConsumingChanges(fileIsImportant=None, change_filter=cf,
                                        onlyImportant=False)
            self.db.schedulers.assertClassifications(self.OBJECTID, { 20 : True })
            self.assertTrue(sched.timer_started)
            self.assertEqual(sched.getPendingBuildTimes(), [ 10 ])
            self.clock.advance(10)
            self.assertEqual(sched.getPendingBuildTimes(), [])
        d.addCallback(check)
        d.addCallback(lambda _ : sched.stopService())
        return d

    def test_gotChange_no_treeStableTimer_unimportant(self):
        sched = self.makeScheduler(self.Subclass, treeStableTimer=None, branch='master')

        sched.startService()

        d = sched.gotChange(self.makeFakeChange(branch='master', number=13), False)
        def check(_):
            self.assertEqual(self.events, [])
        d.addCallback(check)

        d.addCallback(lambda _ : sched.stopService())

    def test_gotChange_no_treeStableTimer_important(self):
        sched = self.makeScheduler(self.Subclass, treeStableTimer=None, branch='master')

        sched.startService()

        d = sched.gotChange(self.makeFakeChange(branch='master', number=13), True)
        def check(_):
            self.assertEqual(self.events, [ 'B[13]@0' ])
        d.addCallback(check)

        d.addCallback(lambda _ : sched.stopService())

    def test_gotChange_treeStableTimer_unimportant(self):
        sched = self.makeScheduler(self.Subclass, treeStableTimer=10, branch='master')

        sched.startService()

        d = sched.gotChange(self.makeFakeChange(branch='master', number=13), False)
        def check(_):
            self.assertEqual(self.events, [])
        d.addCallback(check)
        d.addCallback(lambda _ : self.clock.advance(10))
        d.addCallback(check) # should still be empty

        d.addCallback(lambda _ : sched.stopService())

    def test_gotChange_treeStableTimer_important(self):
        sched = self.makeScheduler(self.Subclass, treeStableTimer=10, branch='master')

        sched.startService()

        d = sched.gotChange(self.makeFakeChange(branch='master', number=13), True)
        d.addCallback(lambda _ : self.clock.advance(10))
        def check(_):
            self.assertEqual(self.events, [ 'B[13]@10' ])
        d.addCallback(check)

        d.addCallback(lambda _ : sched.stopService())

    @defer.inlineCallbacks
    def test_gotChange_treeStableTimer_sequence(self):
        sched = self.makeScheduler(self.Subclass, treeStableTimer=9, branch='master')
        self.master.db.insertTestData([
            fakedb.Change(changeid=1, branch='master', when_timestamp=1110),
            fakedb.ChangeFile(changeid=1, filename='readme.txt'),
            fakedb.Change(changeid=2, branch='master', when_timestamp=2220),
            fakedb.ChangeFile(changeid=2, filename='readme.txt'),
            fakedb.Change(changeid=3, branch='master', when_timestamp=3330),
            fakedb.ChangeFile(changeid=3, filename='readme.txt'),
            fakedb.Change(changeid=4, branch='master', when_timestamp=4440),
            fakedb.ChangeFile(changeid=4, filename='readme.txt'),
        ])
        sched.startService()

        self.clock.advance(2220)

        # this important change arrives at 2220, so the stable timer will last
        # until 2229
        yield sched.gotChange(
                self.makeFakeChange(branch='master', number=1, when=2220),
                True)
        self.assertEqual(self.events, [])
        self.assertEqual(sched.getPendingBuildTimes(), [2229])
        self.db.schedulers.assertClassifications(self.OBJECTID, { 1 : True })

        # but another (unimportant) change arrives before then
        self.clock.advance(6) # to 2226
        self.assertEqual(self.events, [])

        yield sched.gotChange(
                self.makeFakeChange(branch='master', number=2, when=2226),
                False)
        self.assertEqual(self.events, [])
        self.assertEqual(sched.getPendingBuildTimes(), [2235])
        self.db.schedulers.assertClassifications(self.OBJECTID, { 1 : True, 2 : False })

        self.clock.advance(3) # to 2229
        self.assertEqual(self.events, [])

        self.clock.advance(3) # to 2232
        self.assertEqual(self.events, [])

        # another important change arrives at 2232
        yield sched.gotChange(
                self.makeFakeChange(branch='master', number=3, when=2232),
                True)
        self.assertEqual(self.events, [])
        self.assertEqual(sched.getPendingBuildTimes(), [2241])
        self.db.schedulers.assertClassifications(self.OBJECTID, { 1 : True, 2 : False, 3 : True })

        self.clock.advance(3) # to 2235
        self.assertEqual(self.events, [])

        # finally, time to start the build!
        self.clock.advance(6) # to 2241
        self.assertEqual(self.events, [ 'B[1,2,3]@2241' ])
        self.assertEqual(sched.getPendingBuildTimes(), [])
        self.db.schedulers.assertClassifications(self.OBJECTID, { })

        yield sched.stopService()


class SingleBranchScheduler(CommonStuffMixin,
        scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 245

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    def test_constructor_branch_mandatory(self):
        self.assertRaises(config.ConfigErrors,
                lambda : basic.SingleBranchScheduler(name="tsched", treeStableTimer=60))

    def test_constructor_no_branch_but_filter(self):
        # this shouldn't fail
        basic.SingleBranchScheduler(name="tsched", treeStableTimer=60,
                builderNames=['a','b'], change_filter=mock.Mock())

    def test_constructor_branches_forbidden(self):
        self.assertRaises(config.ConfigErrors,
                lambda : basic.SingleBranchScheduler(name="tsched", treeStableTimer=60, branches='x'))

    def test_gotChange_treeStableTimer_important(self):
        # this looks suspiciously like the same test above, because SingleBranchScheduler
        # is about the same as the test subclass used above
        sched = self.makeScheduler(basic.SingleBranchScheduler,
                            treeStableTimer=10, branch='master')

        sched.startService()

        d = sched.gotChange(self.makeFakeChange(branch='master', number=13), True)
        d.addCallback(lambda _ : self.clock.advance(10))
        def check(_):
            self.assertEqual(self.events, [ 'B[13]@10' ])
        d.addCallback(check)

        d.addCallback(lambda _ : sched.stopService())


class AnyBranchScheduler(CommonStuffMixin,
        scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 246

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    def test_constructor_branch_forbidden(self):
        self.assertRaises(config.ConfigErrors,
                lambda : basic.SingleBranchScheduler(name="tsched", treeStableTimer=60, branch='x'))

    def test_gotChange_treeStableTimer_multiple_branches(self):
        """Two changes with different branches get different treeStableTimers"""
        sched = self.makeScheduler(basic.AnyBranchScheduler,
                            treeStableTimer=10, branches=['master', 'devel', 'boring'])

        sched.startService()

        def mkch(**kwargs):
            ch = self.makeFakeChange(**kwargs)
            self.db.changes.fakeAddChangeInstance(ch)
            return ch

        d = defer.succeed(None)
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='master', number=13), True))
        d.addCallback(lambda _ :
                self.assertEqual(sched.getPendingBuildTimes(), [10]))
        d.addCallback(lambda _ :
                self.clock.advance(1)) # time is now 1
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='master', number=14), False))
        d.addCallback(lambda _ :
                self.assertEqual(sched.getPendingBuildTimes(), [11]))
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='boring', number=15), False))
        d.addCallback(lambda _ :
                self.clock.pump([1]*4)) # time is now 5
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='devel', number=16), True))
        d.addCallback(lambda _ :
                self.assertEqual(sorted(sched.getPendingBuildTimes()), [11,15]))
        d.addCallback(lambda _ :
                self.clock.pump([1]*10)) # time is now 15
        def check(_):
            self.assertEqual(self.events, [ 'B[13,14]@11', 'B[16]@15' ])
        d.addCallback(check)

        d.addCallback(lambda _ : sched.stopService())

    def test_gotChange_treeStableTimer_multiple_repositories(self):
        """Two repositories, even with the same branch name, have different treeStableTimers"""
        sched = self.makeScheduler(basic.AnyBranchScheduler,
                            treeStableTimer=10, branches=['master'])

        sched.startService()

        def mkch(**kwargs):
            ch = self.makeFakeChange(**kwargs)
            self.db.changes.fakeAddChangeInstance(ch)
            return ch

        d = defer.succeed(None)
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='master', repository="repo", number=13), True))
        d.addCallback(lambda _ :
                self.clock.advance(1)) # time is now 1
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='master', repository="repo", number=14), False))
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='master', repository="other_repo", number=15), False))
        d.addCallback(lambda _ :
                self.clock.pump([1]*4)) # time is now 5
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='master', repository="other_repo", number=17), True))
        d.addCallback(lambda _ :
                self.clock.pump([1]*10)) # time is now 15
        def check(_):
            self.assertEqual(self.events, [ 'B[13,14]@11', 'B[15,17]@15' ])
        d.addCallback(check)

        d.addCallback(lambda _ : sched.stopService())

    def test_gotChange_treeStableTimer_multiple_projects(self):
        """Two projects, even with the same branch name, have different treeStableTimers"""
        sched = self.makeScheduler(basic.AnyBranchScheduler,
                            treeStableTimer=10, branches=['master'])

        sched.startService()

        def mkch(**kwargs):
            ch = self.makeFakeChange(**kwargs)
            self.db.changes.fakeAddChangeInstance(ch)
            return ch

        d = defer.succeed(None)
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='master', project="proj", number=13), True))
        d.addCallback(lambda _ :
                self.clock.advance(1)) # time is now 1
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='master', project="proj", number=14), False))
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='master', project="other_proj", number=15), False))
        d.addCallback(lambda _ :
                self.clock.pump([1]*4)) # time is now 5
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='master', project="other_proj", number=17), True))
        d.addCallback(lambda _ :
                self.clock.pump([1]*10)) # time is now 15
        def check(_):
            self.assertEqual(self.events, [ 'B[13,14]@11', 'B[15,17]@15' ])
        d.addCallback(check)

        d.addCallback(lambda _ : sched.stopService())

    def test_gotChange_treeStableTimer_multiple_codebases(self):
        """Two codebases, even with the same branch name, have different treeStableTimers"""
        sched = self.makeScheduler(basic.AnyBranchScheduler,
                            treeStableTimer=10, branches=['master'])

        sched.startService()

        def mkch(**kwargs):
            ch = self.makeFakeChange(**kwargs)
            self.db.changes.fakeAddChangeInstance(ch)
            return ch

        d = defer.succeed(None)
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='master', codebase="base", number=13), True))
        d.addCallback(lambda _ :
                self.clock.advance(1)) # time is now 1
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='master', codebase="base", number=14), False))
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='master', codebase="other_base", number=15), False))
        d.addCallback(lambda _ :
                self.clock.pump([1]*4)) # time is now 5
        d.addCallback(lambda _ :
                sched.gotChange(mkch(branch='master', codebase="other_base", number=17), True))
        d.addCallback(lambda _ :
                self.clock.pump([1]*10)) # time is now 15
        def check(_):
            self.assertEqual(self.events, [ 'B[13,14]@11', 'B[15,17]@15' ])
        d.addCallback(check)

        d.addCallback(lambda _ : sched.stopService())
