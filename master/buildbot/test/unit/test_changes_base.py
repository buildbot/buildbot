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
from __future__ import division
from __future__ import print_function

import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.trial import unittest

from buildbot.changes import base
from buildbot.test.util import changesource


class TestChangeSource(changesource.ChangeSourceMixin, unittest.TestCase):
    timeout = 120

    class Subclass(base.ChangeSource):
        pass

    @defer.inlineCallbacks
    def setUp(self):
        yield self.setUpChangeSource()

    def tearDown(self):
        return self.tearDownChangeSource()

    @defer.inlineCallbacks
    def test_activation(self):
        cs = self.Subclass(name="DummyCS")
        cs.activate = mock.Mock(return_value=defer.succeed(None))
        cs.deactivate = mock.Mock(return_value=defer.succeed(None))

        # set the changesourceid, and claim the changesource on another master
        self.attachChangeSource(cs)
        self.setChangeSourceToMaster(self.OTHER_MASTER_ID)

        yield cs.startService()
        cs.clock.advance(cs.POLL_INTERVAL_SEC / 2)
        cs.clock.advance(cs.POLL_INTERVAL_SEC / 5)
        cs.clock.advance(cs.POLL_INTERVAL_SEC / 5)
        self.assertFalse(cs.activate.called)
        self.assertFalse(cs.deactivate.called)
        self.assertFalse(cs.active)
        self.assertEqual(cs.serviceid, self.DUMMY_CHANGESOURCE_ID)

        # clear that masterid
        yield cs.stopService()
        self.setChangeSourceToMaster(None)

        yield cs.startService()
        cs.clock.advance(cs.POLL_INTERVAL_SEC)
        self.assertTrue(cs.activate.called)
        self.assertFalse(cs.deactivate.called)
        self.assertTrue(cs.active)

        # stop the service and see that deactivate is called
        yield cs.stopService()
        self.assertTrue(cs.activate.called)
        self.assertTrue(cs.deactivate.called)
        self.assertFalse(cs.active)


class TestPollingChangeSource(changesource.ChangeSourceMixin, unittest.TestCase):
    timeout = 120

    class Subclass(base.PollingChangeSource):
        pass

    def setUp(self):
        # patch in a Clock so we can manipulate the reactor's time
        self.clock = task.Clock()
        self.patch(reactor, 'callLater', self.clock.callLater)
        self.patch(reactor, 'seconds', self.clock.seconds)

        d = self.setUpChangeSource()

        @d.addCallback
        def create_changesource(_):
            self.attachChangeSource(self.Subclass(name="DummyCS"))
        return d

    def tearDown(self):
        return self.tearDownChangeSource()

    def runClockFor(self, _, secs):
        self.clock.pump([1.0] * secs)

    def test_loop_loops(self):
        # track when poll() gets called
        loops = []
        self.changesource.poll = \
            lambda: loops.append(self.clock.seconds())

        self.changesource.pollInterval = 5
        self.startChangeSource()
        d = defer.Deferred()
        d.addCallback(self.runClockFor, 12)

        @d.addCallback
        def check(_):
            # note that it does *not* poll at time 0
            self.assertEqual(loops, [5.0, 10.0])
        reactor.callWhenRunning(d.callback, None)
        return d

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

        @d.addCallback
        def check(_):
            # note that it keeps looping after error
            self.assertEqual(loops, [5.0, 10.0])
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 2)
        reactor.callWhenRunning(d.callback, None)
        return d

    def test_poll_only_if_activated(self):
        """The polling logic only applies if the source actually starts!"""

        self.setChangeSourceToMaster(self.OTHER_MASTER_ID)

        loops = []
        self.changesource.poll = \
            lambda: loops.append(self.clock.seconds())

        self.changesource.pollInterval = 5
        self.startChangeSource()

        d = defer.Deferred()
        d.addCallback(self.runClockFor, 12)

        @d.addCallback
        def check(_):
            # it doesn't do anything because it was already claimed
            self.assertEqual(loops, [])

        reactor.callWhenRunning(d.callback, None)
        return d

    def test_pollAtLaunch(self):
        # track when poll() gets called
        loops = []
        self.changesource.poll = \
            lambda: loops.append(self.clock.seconds())

        self.changesource.pollInterval = 5
        self.changesource.pollAtLaunch = True
        self.startChangeSource()

        d = defer.Deferred()
        d.addCallback(self.runClockFor, 12)

        @d.addCallback
        def check(_):
            # note that it *does* poll at time 0
            self.assertEqual(loops, [0.0, 5.0, 10.0])
        reactor.callWhenRunning(d.callback, None)
        return d


class TestReconfigurablePollingChangeSource(changesource.ChangeSourceMixin, unittest.TestCase):

    class Subclass(base.ReconfigurablePollingChangeSource):
        pass

    def setUp(self):
        # patch in a Clock so we can manipulate the reactor's time
        self.clock = task.Clock()
        self.patch(reactor, 'callLater', self.clock.callLater)
        self.patch(reactor, 'seconds', self.clock.seconds)

        d = self.setUpChangeSource()

        @d.addCallback
        def create_changesource(_):
            self.attachChangeSource(self.Subclass(name="DummyCS"))
        return d

    def tearDown(self):
        return self.tearDownChangeSource()

    def runClockFor(self, secs):
        self.clock.pump([1.0] * secs)

    @defer.inlineCallbacks
    def test_loop_loops(self):
        # track when poll() gets called
        loops = []
        self.changesource.poll = \
            lambda: loops.append(self.clock.seconds())

        yield self.startChangeSource()
        yield self.changesource.reconfigServiceWithSibling(self.Subclass(
            name="DummyCS", pollInterval=5, pollAtLaunch=False))

        yield self.runClockFor(12)
        # note that it does *not* poll at time 0
        self.assertEqual(loops, [5.0, 10.0])

    @defer.inlineCallbacks
    def test_loop_exception(self):
        # track when poll() gets called
        loops = []

        def poll():
            loops.append(self.clock.seconds())
            raise RuntimeError("oh noes")
        self.changesource.poll = poll

        yield self.startChangeSource()
        yield self.changesource.reconfigServiceWithSibling(self.Subclass(
            name="DummyCS", pollInterval=5, pollAtLaunch=False))

        yield self.runClockFor(12)
        # note that it keeps looping after error
        self.assertEqual(loops, [5.0, 10.0])
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 2)

    @defer.inlineCallbacks
    def test_poll_only_if_activated(self):
        """The polling logic only applies if the source actually starts!"""

        self.setChangeSourceToMaster(self.OTHER_MASTER_ID)

        loops = []
        self.changesource.poll = \
            lambda: loops.append(self.clock.seconds())

        yield self.startChangeSource()
        yield self.changesource.reconfigServiceWithSibling(self.Subclass(
            name="DummyCS", pollInterval=5, pollAtLaunch=False))

        yield self.runClockFor(12)

        # it doesn't do anything because it was already claimed
        self.assertEqual(loops, [])

    @defer.inlineCallbacks
    def test_pollAtLaunch(self):
        # track when poll() gets called
        loops = []
        self.changesource.poll = \
            lambda: loops.append(self.clock.seconds())
        yield self.startChangeSource()
        yield self.changesource.reconfigServiceWithSibling(self.Subclass(
            name="DummyCS", pollInterval=5, pollAtLaunch=True))

        yield self.runClockFor(12)

        # note that it *does* poll at time 0
        self.assertEqual(loops, [0.0, 5.0, 10.0])
