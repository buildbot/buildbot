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
from twisted.internet import defer, reactor, task
from buildbot.test.util import changesource, compat
from buildbot.changes import base

class TestPollingChangeSource(changesource.ChangeSourceMixin, unittest.TestCase):
    class Subclass(base.PollingChangeSource):
        pass

    def setUp(self):
        # patch in a Clock so we can manipulate the reactor's time
        self.clock = task.Clock()
        self.patch(reactor, 'callLater', self.clock.callLater)
        self.patch(reactor, 'seconds', self.clock.seconds)

        d = self.setUpChangeSource()
        def create_changesource(_):
            self.attachChangeSource(self.Subclass())
        d.addCallback(create_changesource)
        return d

    def tearDown(self):
        return self.tearDownChangeSource()

    def runClockFor(self, _, secs):
        self.clock.pump([1.0] * secs)

    def test_loop_loops(self):
        # track when poll() gets called
        loops = []
        self.changesource.poll = \
                lambda : loops.append(self.clock.seconds())

        self.changesource.pollInterval = 5
        self.startChangeSource()

        d = defer.Deferred()
        d.addCallback(self.runClockFor, 12)
        def check(_):
            # note that it does *not* poll at time 0
            self.assertEqual(loops, [5.0, 10.0])
        d.addCallback(check)
        reactor.callWhenRunning(d.callback, None)
        return d

    @compat.usesFlushLoggedErrors
    def test_loop_exception(self):
        # track when poll() gets called
        loops = []
        def poll():
            loops.append(self.clock.seconds())
            raise RuntimeError("oh noes")
        self.changesource.poll = poll

        self.changesource.pollInterval = 5
        self.startChangeSource()

        d = defer.Deferred()
        d.addCallback(self.runClockFor, 12)
        def check(_):
            # note that it keeps looping after error
            self.assertEqual(loops, [5.0, 10.0])
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 2)
        d.addCallback(check)
        reactor.callWhenRunning(d.callback, None)
        return d
