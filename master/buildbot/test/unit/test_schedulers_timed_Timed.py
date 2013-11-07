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

from buildbot.schedulers import timed
from buildbot.test.util import scheduler
from twisted.internet import defer
from twisted.internet import task
from twisted.trial import unittest


class Timed(scheduler.SchedulerMixin, unittest.TestCase):

    OBJECTID = 928754

    def setUp(self):
        self.setUpScheduler()

    def tearDown(self):
        self.tearDownScheduler()

    class Subclass(timed.Timed):

        def getNextBuildTime(self, lastActuation):
            self.got_lastActuation = lastActuation
            return defer.succeed((lastActuation or 1000) + 60)

        def startBuild(self):
            self.started_build = True
            return defer.succeed(None)

    def makeScheduler(self, firstBuildDuration=0, **kwargs):
        sched = self.attachScheduler(self.Subclass(**kwargs), self.OBJECTID)
        self.clock = sched._reactor = task.Clock()
        return sched

    # tests

    # note that most of the heavy-lifting for testing this class is handled by
    # the subclasses' tests, as that's the more natural place for it

    def test_getPendingBuildTimes(self):
        sched = self.makeScheduler(name='test', builderNames=['foo'])

        sched.activate()

        self.assertEqual(sched.got_lastActuation, None)
        self.assertEqual(sched.getPendingBuildTimes(), [1060])

        self.clock.advance(1065)
        self.assertTrue(sched.started_build)
        self.assertEqual(sched.getPendingBuildTimes(), [1120])

        d = sched.deactivate()
        return d
