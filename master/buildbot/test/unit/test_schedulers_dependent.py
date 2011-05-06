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
from buildbot.schedulers import dependent, base
from buildbot.status.results import SUCCESS, WARNINGS, FAILURE
from buildbot.test.util import scheduler
from buildbot.test.fake import fakedb

class Dependent(scheduler.SchedulerMixin, unittest.TestCase):

    SCHEDULERID = 33
    UPSTREAM_NAME = 'uppy'

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    def makeScheduler(self, **kwargs):
        # build a fake upstream scheduler
        class Upstream(base.BaseScheduler):
            def __init__(self, name):
                self.name = name
        upstream = Upstream(self.UPSTREAM_NAME)

        sched = dependent.Dependent(name='n', builderNames=['b'],
                                    upstream=upstream)
        self.attachScheduler(sched, self.SCHEDULERID)
        return sched

    # tests

    # NOTE: these tests take advantage of the fact that all of the fake
    # scheduler operations are synchronous, and thus do not return a Deferred.
    # The Deferred from trigger() is completely processed before this test
    # method returns.

    def test_startService(self):
        sched = self.makeScheduler()
        sched.startService()

        callbacks = self.master.getSubscriptionCallbacks()
        self.assertNotEqual(callbacks['buildsets'], None)
        self.assertNotEqual(callbacks['buildset_completion'], None)

        d = sched.stopService()
        def check(_):
            callbacks = self.master.getSubscriptionCallbacks()
            self.assertEqual(callbacks['buildsets'], None)
            self.assertEqual(callbacks['buildset_completion'], None)
        d.addCallback(check)
        return d

    def do_test(self, scheduler_name, expect_subscription,
            result, expect_buildset):
        sched = self.makeScheduler()
        sched.startService()
        callbacks = self.master.getSubscriptionCallbacks()

        # pretend we saw a buildset with a matching name
        self.db.insertTestData([
            fakedb.SourceStamp(id=93, revision='555', branch='master',
                                project='proj', repository='repo'),
            fakedb.Buildset(id=44, sourcestampid=93),
            ])
        callbacks['buildsets'](bsid=44,
                properties=dict(scheduler=(scheduler_name, 'Scheduler')))

        # check whether scheduler is subscribed to that buildset
        if expect_subscription:
            self.db.buildsets.assertBuildsetSubscriptions((self.SCHEDULERID, 44))
        else:
            self.db.buildsets.assertBuildsetSubscriptions()

        # pretend that the buildset is finished
        self.db.buildsets.fakeBuildsetCompletion(bsid=44, result=result)
        callbacks['buildset_completion'](44, result)

        # and check whether a buildset was added in response
        if expect_buildset:
            self.db.buildsets.assertBuildsets(2)
            bsids = self.db.buildsets.allBuildsetIds()
            bsids.remove(44)
            self.db.buildsets.assertBuildset(bsids[0],
                    dict(external_idstring=None,
                         properties=[('scheduler', ('n', 'Scheduler'))],
                         reason='downstream'),
                    dict(revision='555', branch='master', project='proj',
                         repository='repo'))
        else:
            self.db.buildsets.assertBuildsets(1) # only the one we added above

    def test_related_buildset_SUCCESS(self):
        return self.do_test(self.UPSTREAM_NAME, True, SUCCESS, True)

    def test_related_buildset_WARNINGS(self):
        return self.do_test(self.UPSTREAM_NAME, True, WARNINGS, True)

    def test_related_buildset_FAILURE(self):
        return self.do_test(self.UPSTREAM_NAME, True, FAILURE, False)

    def test_unrelated_buildset(self):
        return self.do_test('unrelated', False, SUCCESS, False)
