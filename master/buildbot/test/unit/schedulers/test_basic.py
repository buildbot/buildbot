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

from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.schedulers import basic
from buildbot.test import fakedb
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import scheduler
from buildbot.test.util.state import StateTestMixin


class CommonStuffMixin:
    @defer.inlineCallbacks
    def makeScheduler(self, klass, **kwargs_override):
        kwargs = {"name": "tsched", "treeStableTimer": 60, "builderNames": ['tbuild']}
        kwargs.update(kwargs_override)

        yield self.master.db.insert_test_data([
            fakedb.Builder(name=builderName) for builderName in kwargs['builderNames']
        ])
        sched = yield self.attachScheduler(klass(**kwargs), self.OBJECTID, self.SCHEDULERID)

        # keep track of builds in self.events
        self.events = []

        @self.assertArgSpecMatches(sched.addBuildsetForChanges)
        def addBuildsetForChanges(
            waited_for=False,
            reason='',
            external_idstring=None,
            changeids=None,
            builderNames=None,
            properties=None,
            priority=None,
            **kw,
        ):
            self.assertEqual(external_idstring, None)
            self.assertEqual(reason, sched.reason)
            self.events.append(f"B{repr(changeids).replace(' ', '')}@{int(self.reactor.seconds())}")
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


class BaseBasicScheduler(
    CommonStuffMixin, scheduler.SchedulerMixin, StateTestMixin, TestReactorMixin, unittest.TestCase
):
    OBJECTID = 244
    SCHEDULERID = 4

    # a custom subclass since we're testing the base class.  This basically
    # re-implements SingleBranchScheduler, but with more asserts
    class Subclass(basic.BaseBasicScheduler):
        timer_started = False

        def getChangeFilter(self, *args, **kwargs):
            return kwargs.get('change_filter')

        def getTimerNameForChange(self, change):
            self.timer_started = True
            return "xxx"

        def getChangeClassificationsForTimer(self, sched_id, timer_name):
            assert timer_name == "xxx"
            assert sched_id == BaseBasicScheduler.SCHEDULERID
            return self.master.db.schedulers.getChangeClassifications(sched_id)

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        yield self.setUpScheduler()

    @defer.inlineCallbacks
    def mkch(self, **kwargs):
        # create changeset and insert in database.
        chd = {"branch": 'master', "project": '', "repository": ''}
        chd.update(kwargs)
        ch = self.makeFakeChange(**chd)
        # fakedb.Change requires changeid instead of number
        chd['changeid'] = chd['number']
        sourcestampid = chd['number'] + 100
        del chd['number']
        yield self.master.db.insert_test_data([
            fakedb.Change(sourcestampid=sourcestampid, **chd),
            fakedb.SourceStamp(id=sourcestampid),
        ])
        return ch

    # tests

    def test_constructor_positional_exception(self):
        with self.assertRaises(TypeError):
            self.Subclass("tsched", "master", 60)

    @defer.inlineCallbacks
    def test_activate_no_treeStableTimer(self):
        cf = mock.Mock('cf')
        fII = mock.Mock('fII')
        yield self.makeScheduler(
            self.Subclass, treeStableTimer=None, change_filter=cf, fileIsImportant=fII
        )

        yield self.master.db.insert_test_data([
            fakedb.SourceStamp(id=92),
            fakedb.Change(changeid=20),
        ])

        yield self.master.db.schedulers.classifyChanges(self.SCHEDULERID, {20: True})

        yield self.master.startService()

        # check that the scheduler has started to consume changes, and the
        # classifications *have* been flushed, since they will not be used
        self.assertConsumingChanges(fileIsImportant=fII, change_filter=cf, onlyImportant=False)
        yield self.assert_classifications(self.SCHEDULERID, {})

    @defer.inlineCallbacks
    def test_activate_treeStableTimer(self):
        cf = mock.Mock()
        sched = yield self.makeScheduler(self.Subclass, treeStableTimer=10, change_filter=cf)

        yield self.master.db.insert_test_data([
            fakedb.SourceStamp(id=92),
            fakedb.Change(changeid=20),
        ])
        yield self.master.db.schedulers.classifyChanges(self.SCHEDULERID, {20: True})

        yield self.master.startService()

        # check that the scheduler has started to consume changes, and no
        # classifications have been flushed.  Furthermore, the existing
        # classification should have been acted on, so the timer should be
        # running
        self.assertConsumingChanges(fileIsImportant=None, change_filter=cf, onlyImportant=False)
        yield self.assert_classifications(self.SCHEDULERID, {20: True})
        self.assertTrue(sched.timer_started)
        self.reactor.advance(10)

    @defer.inlineCallbacks
    def test_gotChange_no_treeStableTimer_unimportant(self):
        sched = yield self.makeScheduler(self.Subclass, treeStableTimer=None, branch='master')
        yield self.master.startService()

        yield sched.gotChange((yield self.mkch(branch='master', number=13)), False)

        self.assertEqual(self.events, [])

    @defer.inlineCallbacks
    def test_gotChange_no_treeStableTimer_important(self):
        sched = yield self.makeScheduler(self.Subclass, treeStableTimer=None, branch='master')

        yield self.master.startService()

        yield sched.gotChange((yield self.mkch(branch='master', number=13)), True)

        self.assertEqual(self.events, ['B[13]@0'])

    @defer.inlineCallbacks
    def test_gotChange_treeStableTimer_unimportant(self):
        sched = yield self.makeScheduler(self.Subclass, treeStableTimer=10, branch='master')
        yield self.master.startService()

        yield sched.gotChange((yield self.mkch(branch='master', number=13)), False)

        self.assertEqual(self.events, [])
        self.reactor.advance(10)
        self.assertEqual(self.events, [])

    @defer.inlineCallbacks
    def test_gotChange_treeStableTimer_important(self):
        sched = yield self.makeScheduler(self.Subclass, treeStableTimer=10, branch='master')

        yield self.master.startService()

        yield sched.gotChange((yield self.mkch(branch='master', number=13)), True)
        self.reactor.advance(10)

        self.assertEqual(self.events, ['B[13]@10'])

    @defer.inlineCallbacks
    def test_gotChange_treeStableTimer_sequence(self):
        sched = yield self.makeScheduler(self.Subclass, treeStableTimer=9, branch='master')
        yield self.master.db.insert_test_data([
            fakedb.SourceStamp(id=92),
            fakedb.Change(changeid=1, branch='master', when_timestamp=1110),
            fakedb.ChangeFile(changeid=1, filename='readme.txt'),
            fakedb.Change(changeid=2, branch='master', when_timestamp=2220),
            fakedb.ChangeFile(changeid=2, filename='readme.txt'),
            fakedb.Change(changeid=3, branch='master', when_timestamp=3330),
            fakedb.ChangeFile(changeid=3, filename='readme.txt'),
            fakedb.Change(changeid=4, branch='master', when_timestamp=4440),
            fakedb.ChangeFile(changeid=4, filename='readme.txt'),
        ])
        yield self.master.startService()

        self.reactor.advance(2220)

        # this important change arrives at 2220, so the stable timer will last
        # until 2229
        yield sched.gotChange(self.makeFakeChange(branch='master', number=1, when=2220), True)
        self.assertEqual(self.events, [])
        yield self.assert_classifications(self.SCHEDULERID, {1: True})

        # but another (unimportant) change arrives before then
        self.reactor.advance(6)  # to 2226
        self.assertEqual(self.events, [])

        yield sched.gotChange(self.makeFakeChange(branch='master', number=2, when=2226), False)
        self.assertEqual(self.events, [])
        yield self.assert_classifications(self.SCHEDULERID, {1: True, 2: False})

        self.reactor.advance(3)  # to 2229
        self.assertEqual(self.events, [])

        self.reactor.advance(3)  # to 2232
        self.assertEqual(self.events, [])

        # another important change arrives at 2232
        yield sched.gotChange(self.makeFakeChange(branch='master', number=3, when=2232), True)
        self.assertEqual(self.events, [])
        yield self.assert_classifications(self.SCHEDULERID, {1: True, 2: False, 3: True})

        self.reactor.advance(3)  # to 2235
        self.assertEqual(self.events, [])

        # finally, time to start the build!
        self.reactor.advance(6)  # to 2241
        self.assertEqual(self.events, ['B[1,2,3]@2241'])
        yield self.assert_classifications(self.SCHEDULERID, {})

    @defer.inlineCallbacks
    def test_enabled_callback(self):
        sched = yield self.makeScheduler(self.Subclass)
        yield self.master.startService()

        expectedValue = not sched.enabled
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, expectedValue)
        expectedValue = not sched.enabled
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, expectedValue)

    @defer.inlineCallbacks
    def test_disabled_activate(self):
        sched = yield self.makeScheduler(self.Subclass)
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        r = yield sched.activate()
        self.assertEqual(r, None)

    @defer.inlineCallbacks
    def test_disabled_deactivate(self):
        sched = yield self.makeScheduler(self.Subclass)
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        r = yield sched.deactivate()
        self.assertEqual(r, None)


class SingleBranchScheduler(
    CommonStuffMixin, scheduler.SchedulerMixin, StateTestMixin, TestReactorMixin, unittest.TestCase
):
    SCHEDULERID = 245
    OBJECTID = 224455

    codebases = {
        'a': {'repository': "", 'branch': 'master'},
        'b': {'repository': "", 'branch': 'master'},
    }

    @defer.inlineCallbacks
    def makeFullScheduler(self, **kwargs):
        yield self.master.db.insert_test_data([
            fakedb.Builder(name=builderName) for builderName in kwargs['builderNames']
        ])
        sched = yield self.attachScheduler(
            basic.SingleBranchScheduler(**kwargs),
            self.OBJECTID,
            self.SCHEDULERID,
            overrideBuildsetMethods=True,
        )
        return sched

    def mkbs(self, **kwargs):
        # create buildset for expected_buildset in assertBuildset.
        bs = {
            "reason": self.sched.reason,
            "external_idstring": None,
            "sourcestampsetid": 100,
            "properties": [('scheduler', ('test', 'Scheduler'))],
        }
        bs.update(kwargs)
        return bs

    def mkss(self, **kwargs):
        # create sourcestamp for expected_sourcestamps in assertBuildset.
        ss = {"branch": 'master', "project": '', "repository": '', "sourcestampsetid": 100}
        ss.update(kwargs)
        return ss

    @defer.inlineCallbacks
    def mkch(self, **kwargs):
        # create changeset and insert in database.
        chd = {"branch": 'master', "project": '', "repository": ''}
        chd.update(kwargs)
        ch = self.makeFakeChange(**chd)
        # fakedb.Change requires changeid instead of number
        chd['changeid'] = chd['number']
        sourcestampid = chd['number'] + 100
        del chd['number']
        yield self.master.db.insert_test_data([
            fakedb.Change(sourcestampid=sourcestampid, **chd),
            fakedb.SourceStamp(id=sourcestampid),
        ])
        return ch

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        yield self.setUpScheduler()

    @defer.inlineCallbacks
    def test_constructor_no_reason(self):
        sched = yield self.makeScheduler(basic.SingleBranchScheduler, branch="master")
        yield sched.configureService()
        self.assertEqual(
            sched.reason, "The SingleBranchScheduler scheduler named 'tsched' triggered this build"
        )

    @defer.inlineCallbacks
    def test_constructor_reason(self):
        sched = yield self.makeScheduler(
            basic.SingleBranchScheduler, branch="master", reason="Changeset"
        )
        yield sched.configureService()
        self.assertEqual(sched.reason, "Changeset")

    def test_constructor_branch_mandatory(self):
        with self.assertRaises(config.ConfigErrors):
            basic.SingleBranchScheduler(name="tsched", treeStableTimer=60)

    def test_constructor_no_branch_but_filter(self):
        # this shouldn't fail
        basic.SingleBranchScheduler(
            name="tsched", treeStableTimer=60, builderNames=['a', 'b'], change_filter=mock.Mock()
        )

    def test_constructor_branches_forbidden(self):
        with self.assertRaises(config.ConfigErrors):
            basic.SingleBranchScheduler(name="tsched", treeStableTimer=60, branches='x')

    @defer.inlineCallbacks
    def test_constructor_priority_none(self):
        sched = yield self.makeScheduler(
            basic.SingleBranchScheduler, branch="master", priority=None
        )
        yield sched.configureService()
        self.assertEqual(sched.priority, None)

    @defer.inlineCallbacks
    def test_constructor_priority_int(self):
        sched = yield self.makeScheduler(basic.SingleBranchScheduler, branch="master", priority=8)
        yield sched.configureService()
        self.assertEqual(sched.priority, 8)

    @defer.inlineCallbacks
    def test_constructor_priority_function(self):
        def sched_priority(builderNames, changesByCodebase):
            return 0

        sched = yield self.makeScheduler(
            basic.SingleBranchScheduler, branch="master", priority=sched_priority
        )
        yield sched.configureService()
        self.assertEqual(sched.priority, sched_priority)

    @defer.inlineCallbacks
    def test_gotChange_treeStableTimer_important(self):
        # this looks suspiciously like the same test above, because SingleBranchScheduler
        # is about the same as the test subclass used above
        sched = yield self.makeScheduler(
            basic.SingleBranchScheduler, treeStableTimer=10, branch='master'
        )

        yield self.master.startService()

        change = yield self.mkch(branch='master', number=13)
        yield sched.gotChange(change, True)
        self.reactor.advance(10)

        self.assertEqual(self.events, ['B[13]@10'])

    @defer.inlineCallbacks
    def test_gotChange_createAbsoluteSourceStamps_saveCodebase(self):
        # check codebase is stored after receiving change.
        sched = yield self.makeFullScheduler(
            name='test',
            builderNames=['test'],
            treeStableTimer=None,
            branch='master',
            codebases=self.codebases,
            createAbsoluteSourceStamps=True,
        )
        yield self.master.db.insert_test_data([
            fakedb.Object(id=self.OBJECTID, name='test', class_name='SingleBranchScheduler')
        ])
        yield self.master.startService()

        yield sched.gotChange(
            (yield self.mkch(codebase='a', revision='1234:abc', repository='A', number=1)), True
        )
        yield sched.gotChange(
            (yield self.mkch(codebase='b', revision='2345:bcd', repository='B', number=2)), True
        )

        yield self.assert_state(
            self.OBJECTID,
            lastCodebases={
                'a': {
                    "branch": 'master',
                    "repository": 'A',
                    "revision": '1234:abc',
                    "lastChange": 1,
                },
                'b': {
                    "branch": 'master',
                    "repository": 'B',
                    "revision": '2345:bcd',
                    "lastChange": 2,
                },
            },
        )

    @defer.inlineCallbacks
    def test_gotChange_createAbsoluteSourceStamps_older_change(self):
        # check codebase is not stored if it's older than the most recent
        sched = yield self.makeFullScheduler(
            name='test',
            builderNames=['test'],
            treeStableTimer=None,
            branch='master',
            codebases=self.codebases,
            createAbsoluteSourceStamps=True,
        )
        yield self.master.db.insert_test_data([
            fakedb.Object(id=self.OBJECTID, name='test', class_name='SingleBranchScheduler'),
            fakedb.ObjectState(
                objectid=self.OBJECTID,
                name='lastCodebases',
                value_json='{"a": {"branch": "master", "repository": "A", '
                '"revision": "5555:def",  "lastChange": 20}}',
            ),
        ])

        yield self.master.startService()

        # this change is not recorded, since it's older than
        # change 20
        yield sched.gotChange(
            (yield self.mkch(codebase='a', revision='1234:abc', repository='A', number=10)), True
        )

        yield self.assert_state(
            self.OBJECTID,
            lastCodebases={
                'a': {
                    "branch": 'master',
                    "repository": 'A',
                    "revision": '5555:def',
                    "lastChange": 20,
                }
            },
        )

    @defer.inlineCallbacks
    def test_getCodebaseDict(self):
        sched = yield self.makeFullScheduler(
            name='test',
            builderNames=['test'],
            treeStableTimer=None,
            branch='master',
            codebases=self.codebases,
            createAbsoluteSourceStamps=True,
        )
        yield self.master.startService()
        sched._lastCodebases = {
            'a': {"branch": 'master', "repository": 'A', "revision": '5555:def', "lastChange": 20}
        }

        cbd = yield sched.getCodebaseDict('a')
        self.assertEqual(
            cbd, {"branch": 'master', "repository": 'A', "revision": '5555:def', "lastChange": 20}
        )

    @defer.inlineCallbacks
    def test_getCodebaseDict_no_createAbsoluteSourceStamps(self):
        sched = yield self.makeFullScheduler(
            name='test',
            builderNames=['test'],
            treeStableTimer=None,
            branch='master',
            codebases=self.codebases,
            createAbsoluteSourceStamps=False,
        )
        yield self.master.startService()
        sched._lastCodebases = {
            'a': {"branch": 'master', "repository": 'A', "revision": '5555:def', "lastChange": 20}
        }

        cbd = yield sched.getCodebaseDict('a')
        # _lastCodebases is ignored
        self.assertEqual(cbd, {'branch': 'master', 'repository': ''})

    @defer.inlineCallbacks
    def test_gotChange_with_priority(self):
        sched = yield self.makeFullScheduler(
            name='test', builderNames=['test'], branch='master', priority=8
        )
        yield self.master.db.insert_test_data([
            fakedb.Object(id=self.OBJECTID, name='test', class_name='SingleBranchScheduler')
        ])

        yield self.master.startService()

        yield sched.gotChange(
            (yield self.mkch(codebase='a', revision='1234:abc', repository='A', number=10)), True
        )

        self.assertEqual(
            self.addBuildsetCalls,
            [
                (
                    'addBuildsetForChanges',
                    {
                        'waited_for': False,
                        'external_idstring': None,
                        'changeids': [10],
                        'properties': None,
                        'reason': "The SingleBranchScheduler scheduler named 'test' triggered this build",
                        'builderNames': None,
                        'priority': 8,
                    },
                )
            ],
        )


class AnyBranchScheduler(
    CommonStuffMixin, scheduler.SchedulerMixin, TestReactorMixin, unittest.TestCase
):
    SCHEDULERID = 6
    OBJECTID = 246

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        yield self.setUpScheduler()

    def test_constructor_branch_forbidden(self):
        with self.assertRaises(config.ConfigErrors):
            basic.SingleBranchScheduler(name="tsched", treeStableTimer=60, branch='x')

    @defer.inlineCallbacks
    def test_gotChange_treeStableTimer_multiple_branches(self):
        """Two changes with different branches get different treeStableTimers"""
        sched = yield self.makeScheduler(
            basic.AnyBranchScheduler, treeStableTimer=10, branches=['master', 'devel', 'boring']
        )

        yield self.master.startService()

        @defer.inlineCallbacks
        def mkch(**kwargs):
            ch = self.makeFakeChange(**kwargs)
            ch = yield self.addFakeChange(ch)
            return ch

        yield sched.gotChange((yield mkch(branch='master', number=500)), True)
        yield self.reactor.advance(1)  # time is now 1
        yield sched.gotChange((yield mkch(branch='master', number=501)), False)
        yield sched.gotChange((yield mkch(branch='boring', number=502)), False)
        yield self.reactor.pump([1] * 4)  # time is now 5
        yield sched.gotChange((yield mkch(branch='devel', number=503)), True)
        yield self.reactor.pump([1] * 10)  # time is now 15

        self.assertEqual(self.events, ['B[500,501]@11', 'B[503]@15'])

    @defer.inlineCallbacks
    def test_gotChange_treeStableTimer_multiple_repositories(self):
        """Two repositories, even with the same branch name, have different treeStableTimers"""
        sched = yield self.makeScheduler(
            basic.AnyBranchScheduler, treeStableTimer=10, branches=['master']
        )

        yield self.master.startService()

        @defer.inlineCallbacks
        def mkch(**kwargs):
            ch = self.makeFakeChange(**kwargs)
            ch = yield self.addFakeChange(ch)
            return ch

        yield sched.gotChange((yield mkch(branch='master', repository="repo", number=500)), True)
        yield self.reactor.advance(1)  # time is now 1
        yield sched.gotChange((yield mkch(branch='master', repository="repo", number=501)), False)
        yield sched.gotChange(
            (yield mkch(branch='master', repository="other_repo", number=502)), False
        )
        yield self.reactor.pump([1] * 4)  # time is now 5
        yield sched.gotChange(
            (yield mkch(branch='master', repository="other_repo", number=503)), True
        )
        yield self.reactor.pump([1] * 10)  # time is now 15

        self.assertEqual(self.events, ['B[500,501]@11', 'B[502,503]@15'])

    @defer.inlineCallbacks
    def test_gotChange_treeStableTimer_multiple_projects(self):
        """Two projects, even with the same branch name, have different treeStableTimers"""
        sched = yield self.makeScheduler(
            basic.AnyBranchScheduler, treeStableTimer=10, branches=['master']
        )

        yield self.master.startService()

        @defer.inlineCallbacks
        def mkch(**kwargs):
            ch = self.makeFakeChange(**kwargs)
            ch = yield self.addFakeChange(ch)
            return ch

        yield sched.gotChange((yield mkch(branch='master', project="proj", number=500)), True)
        yield self.reactor.advance(1)  # time is now 1
        yield sched.gotChange((yield mkch(branch='master', project="proj", number=501)), False)
        yield sched.gotChange(
            (yield mkch(branch='master', project="other_proj", number=502)), False
        )
        yield self.reactor.pump([1] * 4)  # time is now 5
        yield sched.gotChange((yield mkch(branch='master', project="other_proj", number=503)), True)
        yield self.reactor.pump([1] * 10)  # time is now 15

        self.assertEqual(self.events, ['B[500,501]@11', 'B[502,503]@15'])

    @defer.inlineCallbacks
    def test_gotChange_treeStableTimer_multiple_codebases(self):
        """Two codebases, even with the same branch name, have different treeStableTimers"""
        sched = yield self.makeScheduler(
            basic.AnyBranchScheduler, treeStableTimer=10, branches=['master']
        )

        yield self.master.startService()

        @defer.inlineCallbacks
        def mkch(**kwargs):
            ch = self.makeFakeChange(**kwargs)
            ch = yield self.addFakeChange(ch)
            return ch

        yield sched.gotChange((yield mkch(branch='master', codebase="base", number=500)), True)
        self.reactor.advance(1)  # time is now 1
        yield sched.gotChange((yield mkch(branch='master', codebase="base", number=501)), False)
        yield sched.gotChange(
            (yield mkch(branch='master', codebase="other_base", number=502)), False
        )
        self.reactor.pump([1] * 4)  # time is now 5
        yield sched.gotChange(
            (yield mkch(branch='master', codebase="other_base", number=503)), True
        )
        self.reactor.pump([1] * 10)  # time is now 15

        self.assertEqual(self.events, ['B[500,501]@11', 'B[502,503]@15'])
