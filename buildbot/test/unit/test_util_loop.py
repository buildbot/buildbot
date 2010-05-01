# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla-specific Buildbot steps.
#
# The Initial Developer of the Original Code is
# Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Brian Warner <warner@lothar.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

from twisted.trial import unittest
from twisted.internet import reactor, defer, task
from twisted.application import service
from twisted.python import log

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
        reactor = self.loop._reactor = task.Clock()
        eventual._setReactor(reactor)
        state = State(count=5)
        def proc():
            self.results.append(reactor.seconds())
            state.count -= 1
            if state.count:
                return defer.succeed(reactor.seconds() + 10.0)
        self.loop.add(proc)
        self.loop.trigger()
        def check(ign):
            reactor.pump((0,) + (1,)*50) # run for 50 fake seconds
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
