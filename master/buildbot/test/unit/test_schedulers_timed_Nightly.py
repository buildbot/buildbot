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

import datetime
import time

import mock

from twisted.internet import defer
from twisted.internet import task
from twisted.python import log
from twisted.trial import unittest

from buildbot.changes import filter
from buildbot.schedulers import timed
from buildbot.test.fake import fakedb
from buildbot.test.util import scheduler


class Nightly(scheduler.SchedulerMixin, unittest.TestCase):

    try:
        datetime.datetime.fromtimestamp(1)
    except OSError:
        skip = ("Python 3.6 bug on Windows: "
                "https://bugs.python.org/issue29097")

    OBJECTID = 132
    SCHEDULERID = 32

    # not all timezones are even multiples of 1h from GMT.  This variable
    # holds the number of seconds ahead of the hour for the current timezone.
    # This is then added to the clock before each test is run (to get to 0
    # minutes past the hour) and subtracted before the time offset is reported.
    localtime_offset = time.timezone % 3600

    def makeScheduler(self, **kwargs):
        sched = self.attachScheduler(timed.Nightly(**kwargs),
                                     self.OBJECTID, self.SCHEDULERID,
                                     overrideBuildsetMethods=True)

        self.master.db.insertTestData(
            [fakedb.Builder(name=bname) for bname in kwargs.get("builderNames", [])])

        # add a Clock to help checking timing issues
        self.clock = sched._reactor = task.Clock()
        self.clock.advance(self.localtime_offset)  # get to 0 min past the hour

        self.addBuildsetCallTimes = []

        def recordTimes(timeList, method):
            def timedMethod(**kw):
                timeList.append(self.clock.seconds() - self.localtime_offset)
                return method(**kw)
            return timedMethod

        sched.addBuildsetForSourceStampsWithDefaults = recordTimes(
            self.addBuildsetCallTimes,
            sched.addBuildsetForSourceStampsWithDefaults)
        sched.addBuildsetForChanges = recordTimes(
            self.addBuildsetCallTimes,
            sched.addBuildsetForChanges)

        # see self.assertConsumingChanges
        self.consumingChanges = None

        def startConsumingChanges(**kwargs):
            self.consumingChanges = kwargs
            return defer.succeed(None)
        sched.startConsumingChanges = startConsumingChanges

        return sched

    def mkbs(self, **kwargs):
        # create buildset for expected_buildset in assertBuildset.
        bs = dict(reason="The Nightly scheduler named 'test' triggered this build", external_idstring='', sourcestampsetid=100,
                  properties=[('scheduler', ('test', 'Scheduler'))])
        bs.update(kwargs)
        return bs

    def mkss(self, **kwargs):
        # create sourcestamp for expected_sourcestamps in assertBuildset.
        ss = dict(
            branch='master', project='', repository='', sourcestampsetid=100)
        ss.update(kwargs)
        return ss

    def mkch(self, **kwargs):
        # create changeset and insert in database.
        chd = dict(branch='master', project='', repository='')
        chd.update(kwargs)
        ch = self.makeFakeChange(**chd)
        # fakedb.Change requires changeid instead of number
        chd['changeid'] = chd['number']
        del chd['number']
        self.db.insertTestData([fakedb.Change(**chd)])
        return ch

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    def assertConsumingChanges(self, **kwargs):
        self.assertEqual(self.consumingChanges, kwargs)

    # Tests

    def test_constructor_no_reason(self):
        sched = self.makeScheduler(
            name='test', builderNames=['test'], branch='default')
        self.assertEqual(
            sched.reason, "The Nightly scheduler named 'test' triggered this build")

    def test_constructor_reason(self):
        sched = self.makeScheduler(
            name='test', builderNames=['test'], branch='default', reason="hourly")
        self.assertEqual(sched.reason, "hourly")

    def test_constructor_change_filter(self):
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   branch=None, change_filter=filter.ChangeFilter(category_re="fo+o"))
        assert sched.change_filter

    def test_constructor_month(self):
        sched = self.makeScheduler(
            name='test', builderNames=['test'], branch='default', month='1')
        self.assertEqual(sched.month, "1")

    @defer.inlineCallbacks
    def test_enabled_callback(self):
        sched = self.makeScheduler(
            name='test', builderNames=['test'], branch='default')
        expectedValue = not sched.enabled
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, expectedValue)
        expectedValue = not sched.enabled
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, expectedValue)

    @defer.inlineCallbacks
    def test_disabled_activate(self):
        sched = self.makeScheduler(
            name='test', builderNames=['test'], branch='default')
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        r = yield sched.activate()
        self.assertEqual(r, None)

    @defer.inlineCallbacks
    def test_disabled_deactivate(self):
        sched = self.makeScheduler(
            name='test', builderNames=['test'], branch='default')
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        r = yield sched.deactivate()
        self.assertEqual(r, None)

    @defer.inlineCallbacks
    def test_disabled_start_build(self):
        sched = self.makeScheduler(
            name='test', builderNames=['test'], branch='default')
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        r = yield sched.startBuild()
        self.assertEqual(r, None)

    # end-to-end tests: let's see the scheduler in action

    @defer.inlineCallbacks
    def test_iterations_simple(self):
        # note that Nightly works in local time, but the task.Clock() always
        # starts at midnight UTC, so be careful not to use times that are
        # timezone dependent -- stick to minutes-past-the-half-hour, as some
        # timezones are multiples of 30 minutes off from UTC
        sched = self.makeScheduler(name='test', builderNames=['test'], branch=None,
                                   minute=[10, 20, 21, 40, 50, 51])

        # add a change classification
        self.db.schedulers.fakeClassifications(self.SCHEDULERID, {19: True})

        yield sched.activate()

        # check that the classification has been flushed, since this
        # invocation has not requested onlyIfChanged
        self.db.schedulers.assertClassifications(self.SCHEDULERID, {})

        self.clock.advance(0)  # let it get set up
        while self.clock.seconds() < self.localtime_offset + 30 * 60:
            self.clock.advance(60)
        self.assertEqual(self.addBuildsetCallTimes, [600, 1200, 1260])
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', {
                'builderNames': None,
                'sourcestamps': [{'codebase': ''}],
                'properties': None,
                'reason': u"The Nightly scheduler named 'test' triggered this build",
                'waited_for': False}),
            ('addBuildsetForSourceStampsWithDefaults', {
                'builderNames': None,
                'sourcestamps': [{'codebase': ''}],
                'properties': None,
                'reason': u"The Nightly scheduler named 'test' triggered this build",
                'waited_for': False}),
            ('addBuildsetForSourceStampsWithDefaults', {
                'builderNames': None,
                'sourcestamps': [{'codebase': ''}],
                'properties': None,
                'reason': u"The Nightly scheduler named 'test' triggered this build",
                'waited_for': False})])
        self.db.state.assertStateByClass('test', 'Nightly',
                                         last_build=1260 + self.localtime_offset)

        yield sched.deactivate()

    def test_iterations_simple_with_branch(self):
        # see timezone warning above
        sched = self.makeScheduler(name='test', builderNames=['test'],
                                   branch='master', minute=[5, 35])

        sched.activate()

        self.clock.advance(0)
        while self.clock.seconds() < self.localtime_offset + 10 * 60:
            self.clock.advance(60)
        self.assertEqual(self.addBuildsetCallTimes, [300])
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForSourceStampsWithDefaults', {
                'builderNames': None,
                'sourcestamps': [{'codebase': ''}],
                'properties': None,
                'reason': u"The Nightly scheduler named 'test' triggered this build",
                'waited_for': False})])
        self.db.state.assertStateByClass('test', 'Nightly',
                                         last_build=300 + self.localtime_offset)

        d = sched.deactivate()
        return d

    def do_test_iterations_onlyIfChanged(self, *changes_at, **kwargs):
        fII = mock.Mock(name='fII')
        self.makeScheduler(name='test', builderNames=['test'], branch=None,
                           minute=[5, 25, 45], onlyIfChanged=True,
                           fileIsImportant=fII, **kwargs)

        return self.do_test_iterations_onlyIfChanged_test(fII, *changes_at)

    @defer.inlineCallbacks
    def do_test_iterations_onlyIfChanged_test(self, fII, *changes_at):
        yield self.sched.activate()

        # check that the scheduler has started to consume changes
        self.assertConsumingChanges(fileIsImportant=fII, change_filter=None,
                                    onlyImportant=False)

        # manually run the clock forward through a half-hour, allowing any
        # excitement to take place
        changes_at = list(changes_at)
        self.clock.advance(0)  # let it trigger the first build
        while self.clock.seconds() < self.localtime_offset + 30 * 60:
            # inject any new changes..
            while (changes_at and
                    self.clock.seconds() >=
                   self.localtime_offset + changes_at[0][0]):
                when, newchange, important = changes_at.pop(0)
                self.db.changes.fakeAddChangeInstance(newchange)
                yield self.sched.gotChange(newchange, important).addErrback(log.err)
            # and advance the clock by a minute
            self.clock.advance(60)

    @defer.inlineCallbacks
    def test_iterations_onlyIfChanged_no_changes(self):
        yield self.do_test_iterations_onlyIfChanged()
        self.assertEqual(self.addBuildsetCalls, [])
        self.db.state.assertStateByClass('test', 'Nightly',
                                         last_build=1500 + self.localtime_offset)
        yield self.sched.deactivate()

    @defer.inlineCallbacks
    def test_iterations_onlyIfChanged_unimp_changes(self):
        yield self.do_test_iterations_onlyIfChanged(
            (60, mock.Mock(), False),
            (600, mock.Mock(), False))
        self.assertEqual(self.addBuildsetCalls, [])
        self.db.state.assertStateByClass('test', 'Nightly',
                                         last_build=1500 + self.localtime_offset)
        yield self.sched.deactivate()

    @defer.inlineCallbacks
    def test_iterations_onlyIfChanged_off_branch_changes(self):
        yield self.do_test_iterations_onlyIfChanged(
            (60, self.makeFakeChange(number=1, branch='testing'), True),
            (1700, self.makeFakeChange(number=2, branch='staging'), True))
        self.assertEqual(self.addBuildsetCalls, [])
        self.db.state.assertStateByClass('test', 'Nightly',
                                         last_build=1500 + self.localtime_offset)
        yield self.sched.deactivate()

    @defer.inlineCallbacks
    def test_iterations_onlyIfChanged_mixed_changes(self):
        yield self.do_test_iterations_onlyIfChanged(
            (120, self.makeFakeChange(number=3, branch=None), False),
            (130, self.makeFakeChange(number=4, branch='offbranch'), True),
            (1200, self.makeFakeChange(number=5, branch=None), True),
            (1201, self.makeFakeChange(number=6, branch=None), False),
            (1202, self.makeFakeChange(number=7, branch='offbranch'), True))
        # note that the changeid list includes the unimportant changes, but not the
        # off-branch changes, and note that no build took place at 300s, as no important
        # changes had yet arrived
        self.assertEqual(self.addBuildsetCallTimes, [1500])
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForChanges', {
                'builderNames': None,
                'changeids': [3, 5, 6],
                'external_idstring': None,
                'properties': None,
                'reason': u"The Nightly scheduler named 'test' triggered this build",
                'waited_for': False})])
        self.db.state.assertStateByClass('test', 'Nightly',
                                         last_build=1500 + self.localtime_offset)
        yield self.sched.deactivate()

    @defer.inlineCallbacks
    def test_iterations_onlyIfChanged_createAbsoluteSourceStamps_oneChanged(self):
        # Test createAbsoluteSourceStamps=True when only one codebase has
        # changed
        yield self.do_test_iterations_onlyIfChanged(
            (120, self.makeFakeChange(
                number=3, codebase='a', revision='2345:bcd'), True),
            codebases={'a': {'repository': "", 'branch': 'master'},
                       'b': {'repository': "", 'branch': 'master'}},
            createAbsoluteSourceStamps=True)
        self.db.state.assertStateByClass('test', 'Nightly',
                                         last_build=1500 + self.localtime_offset)
        # addBuildsetForChanges calls getCodebase, so this isn't too
        # interesting
        self.assertEqual(self.addBuildsetCallTimes, [300])
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForChanges', {
                'builderNames': None,
                'changeids': [3],
                'external_idstring': None,
                'properties': None,
                'reason': u"The Nightly scheduler named 'test' triggered this build",
                'waited_for': False})])
        self.db.state.assertStateByClass('test', 'Nightly', lastCodebases={
            'a': dict(revision='2345:bcd', branch=None, repository='', lastChange=3)})
        yield self.sched.deactivate()

    @defer.inlineCallbacks
    def test_iterations_onlyIfChanged_createAbsoluteSourceStamps_oneChanged_loadOther(self):
        # Test createAbsoluteSourceStamps=True when only one codebase has changed,
        # but the other was previously changed
        fII = mock.Mock(name='fII')
        self.makeScheduler(name='test', builderNames=['test'], branch=None,
                           minute=[5, 25, 45], onlyIfChanged=True,
                           fileIsImportant=fII,
                           codebases={'a': {'repository': "", 'branch': 'master'},
                                      'b': {'repository': "", 'branch': 'master'}},
                           createAbsoluteSourceStamps=True)

        self.db.insertTestData([
            fakedb.Object(id=self.OBJECTID, name='test', class_name='Nightly'),
            fakedb.ObjectState(objectid=self.OBJECTID, name='lastCodebases',
                               value_json='{"b": {"branch": "master", "repository": "B", "revision": "1234:abc",  "lastChange": 2}}')])

        yield self.do_test_iterations_onlyIfChanged_test(fII,
                                                         (120, self.makeFakeChange(number=3, codebase='a', revision='2345:bcd'), True))

        self.db.state.assertStateByClass('test', 'Nightly',
                                         last_build=1500 + self.localtime_offset)
        # addBuildsetForChanges calls getCodebase, so this isn't too
        # interesting
        self.assertEqual(self.addBuildsetCallTimes, [300])
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForChanges', {
                'builderNames': None,
                'changeids': [3],
                'external_idstring': None,
                'properties': None,
                'reason': u"The Nightly scheduler named 'test' triggered this build",
                'waited_for': False})])
        self.db.state.assertStateByClass('test', 'Nightly', lastCodebases={
            'a': dict(revision='2345:bcd', branch=None, repository='', lastChange=3),
            'b': dict(revision='1234:abc', branch="master", repository='B', lastChange=2)})
        yield self.sched.deactivate()

    @defer.inlineCallbacks
    def test_iterations_onlyIfChanged_createAbsoluteSourceStamps_bothChanged(self):
        # Test createAbsoluteSourceStamps=True when both codebases have changed
        yield self.do_test_iterations_onlyIfChanged(
            (120, self.makeFakeChange(
                number=3, codebase='a', revision='2345:bcd'), True),
            (122, self.makeFakeChange(
                number=4, codebase='b', revision='1234:abc'), True),
            codebases={'a': {'repository': "", 'branch': 'master'},
                       'b': {'repository': "", 'branch': 'master'}},
            createAbsoluteSourceStamps=True)
        self.db.state.assertStateByClass('test', 'Nightly',
                                         last_build=1500 + self.localtime_offset)
        # addBuildsetForChanges calls getCodebase, so this isn't too
        # interesting
        self.assertEqual(self.addBuildsetCallTimes, [300])
        self.assertEqual(self.addBuildsetCalls, [
            ('addBuildsetForChanges', {
                'builderNames': None,
                'changeids': [3, 4],
                'external_idstring': None,
                'properties': None,
                'reason': u"The Nightly scheduler named 'test' triggered this build",
                'waited_for': False})])
        self.db.state.assertStateByClass('test', 'Nightly', lastCodebases={
            'a': dict(revision='2345:bcd', branch=None, repository='', lastChange=3),
            'b': dict(revision='1234:abc', branch=None, repository='', lastChange=4)})
        yield self.sched.deactivate()
