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
from twisted.internet import reactor, defer, task
from twisted.application import service

from buildbot.test.fake.state import State

from buildbot.util import loop, eventual

class TestLoopMixin(object):
    def setUpTestLoop(self, skipConstructor=False):
        if not skipConstructor:
            self.loop = loop.Loop()
            self.loop.startService()
        self.results = []

    def tearDownTestLoop(self):
        eventual._setReactor(None)
        assert self.loop.is_quiet()
        return self.loop.stopService()

    # create a simple common callback with a tag that will
    # appear in self.results
    def make_cb(self, tag, selfTrigger=None):
        state = State(triggerCount = selfTrigger)
        def cb():
            if selfTrigger:
                self.results.append("%s-%d" % (tag, state.triggerCount))
                state.triggerCount -= 1
                if state.triggerCount > 0:
                    self.loop.trigger()
            else:
                self.results.append(tag)
        return cb

    # wait for quiet, and call check with self.results.
    # Returns a deferred.
    def whenQuiet(self, check=lambda res : None):
        d = self.loop.when_quiet()
        d.addCallback(lambda _ : check(self.results))
        return d

class Loop(unittest.TestCase, TestLoopMixin):

    def setUp(self):
        self.setUpTestLoop()

    def tearDown(self):
        self.tearDownTestLoop()

    def test_single_processor(self):
        self.loop.add(self.make_cb('x'))
        self.loop.trigger()
        def check(res):
            self.assertEqual(res, ['x'])
        return self.whenQuiet(check)

    def test_multi_processor(self):
        self.loop.add(self.make_cb('x'))
        self.loop.add(self.make_cb('y'))
        self.loop.add(self.make_cb('z'))
        self.loop.trigger()
        def check(res):
            self.assertEqual(sorted(res), ['x', 'y', 'z'])
        return self.whenQuiet(check)

    def test_big_multi_processor(self):
        for i in range(300):
            self.loop.add(self.make_cb(i))
        def check(res):
            self.assertEqual(sorted(res), range(300))
        self.loop.trigger()
        d = self.whenQuiet(check)
        return d

    def test_simple_selfTrigger(self):
        self.loop.add(self.make_cb('c', selfTrigger=3))
        self.loop.trigger()
        def check(res):
            self.assertEqual(sorted(res), ['c-1', 'c-2', 'c-3'])
        return self.whenQuiet(check)

    def test_multi_selfTrigger(self):
        self.loop.add(self.make_cb('c', selfTrigger=3))
        self.loop.add(self.make_cb('d')) # will get taken along
        self.loop.trigger()
        def check(res):
            self.assertEqual(sorted(res), ['c-1', 'c-2', 'c-3', 'd', 'd', 'd'])
        return self.whenQuiet(check)

    def test_multi_sequential(self):
        state = State(in_proc=False, entries=0)
        for i in range(10):
            def cb():
                state.entries += 1
                assert not state.in_proc
                state.in_proc = True
                d = defer.Deferred()
                def finish():
                    assert state.in_proc
                    state.in_proc = False
                    d.callback(None)
                reactor.callLater(0, finish)
                return d
            self.loop.add(cb)
        self.loop.trigger()
        def check(res):
            self.assertEqual(state.entries, 10)
        return self.whenQuiet(check)

    def test_sleep(self):
        clock_reactor = self.loop._reactor = task.Clock()
        eventual._setReactor(clock_reactor)
        state = State(count=5)
        def proc():
            self.results.append(clock_reactor.seconds())
            state.count -= 1
            if state.count:
                return defer.succeed(clock_reactor.seconds() + 10.0)
        self.loop.add(proc)
        self.loop.trigger()
        def check(ign):
            clock_reactor.pump((0,) + (1,)*50) # run for 50 fake seconds
            self.assertEqual(self.results, [ 0.0, 10.0, 20.0, 30.0, 40.0 ])
        d = eventual.flushEventualQueue()
        d.addCallback(check)
        return d

    def test_loop_done(self):
        # monkey-patch the instance to have a 'loop_done' method
        # which just modifies 'done' to indicate that it was called
        def loop_done():
            self.results.append("done")
        self.patch(self.loop, "loop_done", loop_done)

        self.loop.add(self.make_cb('t', selfTrigger=2))
        self.loop.trigger()
        def check(res):
            self.assertEqual(res, [ 't-2', 't-1', 'done' ])
        return self.whenQuiet(check)

    def test_mergeTriggers(self):
        state = State(count=4)
        def make_proc(): # without this, proc will only be added to the loop once
            def proc():
                self.results.append("p")
                if state.count > 0:
                    self.results.append("t")
                    self.loop.trigger()
                state.count -= 1
            return proc
        self.loop.add(make_proc())
        self.loop.add(make_proc())
        self.loop.trigger()
        # there should be four triggers, and three runs of the loop
        def check(res):
            self.assertEqual(res, [ 'p', 't', 'p', 't', 'p', 't', 'p', 't', 'p', 'p' ])
        return self.whenQuiet(check)

class DelegateLoop(unittest.TestCase, TestLoopMixin):

    def setUp(self):
        self.setUpTestLoop(skipConstructor=True)

    def tearDown(self):
        self.tearDownTestLoop()

    # DelegateLoop doesn't contain much logic, so we don't re-test all of the
    # functionality we tested with Loop

    def test_get_processors(self):
        def get_processors():
            def proc(): self.results.append("here")
            return [ proc ]
        self.loop = loop.DelegateLoop(get_processors)
        self.loop.startService()
        self.loop.trigger()
        def check(res):
            self.assertEqual(res, [ "here" ])
        return self.whenQuiet(check)

class MultiServiceLoop(unittest.TestCase, TestLoopMixin):

    def setUp(self):
        self.setUpTestLoop(skipConstructor=True)
        self.loop = loop.MultiServiceLoop()

    def tearDown(self):
        self.tearDownTestLoop()

    # MultiServiceLoop doesn't contain much logic, so we don't re-test all of
    # the functionality we tested with Loop

    class ServiceWithProcess(service.Service):
        did_run = False
        def run(self):
            self.did_run = True

    def test_serviceChild(self):
        childsvc = self.ServiceWithProcess()
        childsvc.setServiceParent(self.loop)
        self.loop.startService()
        self.loop.trigger()
        def check(res):
            self.assertTrue(childsvc.did_run)
        return self.whenQuiet(check)
