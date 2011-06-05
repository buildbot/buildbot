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
from twisted.internet import defer, reactor
from twisted.python import failure
from buildbot.test.util import compat
from buildbot.process import botmaster
from buildbot.util import epoch2datetime

class Test(unittest.TestCase):

    def setUp(self):
        self.botmaster = mock.Mock(name='botmaster')
        self.botmaster.builders = {}
        def prioritizeBuilders(master, builders):
            # simple sort-by-name by default
            return sorted(builders, lambda b1,b2 : cmp(b1.name, b2.name))
        self.botmaster.prioritizeBuilders = prioritizeBuilders
        self.master = self.botmaster.master = mock.Mock(name='master')
        self.brd = botmaster.BuildRequestDistributor(self.botmaster)
        self.brd.startService()

        # TODO: this is a terrible way to detect the "end" of the test -
        # it regularly completes too early after a simple modification of
        # a test.  Is there a better way?
        self.quiet_deferred = defer.Deferred()
        def _quiet():
            if self.quiet_deferred:
                d, self.quiet_deferred = self.quiet_deferred, None
                d.callback(None)
            else:
                self.fail("loop has already gone quiet once")
        self.brd._quiet = _quiet

        self.maybeStartBuild_calls = []
        self.builders = {}

    def tearDown(self):
        if self.brd.running:
            return self.brd.stopService()

    def addBuilders(self, names):
        for name in names:
            bldr = mock.Mock(name=name)
            self.botmaster.builders[name] = bldr
            self.builders[name] = bldr
            def maybeStartBuild(n=name):
                self.maybeStartBuild_calls.append(n)
                d = defer.Deferred()
                reactor.callLater(0, d.callback, None)
                return d
            bldr.maybeStartBuild = maybeStartBuild
            bldr.name = name

    def removeBuilder(self, name):
        del self.builders[name]
        del self.botmaster.builders[name]

    # tests

    def test_maybeStartBuildsOn_simple(self):
        self.addBuilders(['bldr1'])
        self.brd.maybeStartBuildsOn(['bldr1'])
        def check(_):
            self.assertEqual(self.maybeStartBuild_calls, ['bldr1'])
        self.quiet_deferred.addCallback(check)
        return self.quiet_deferred

    def test_maybeStartBuildsOn_parallel(self):
        # test 15 "parallel" invocations of maybeStartBuildsOn, with a
        # _sortBuilders that takes a while.  This is a regression test for bug
        # #1979.
        builders = ['bldr%02d' % i for i in xrange(15) ]

        def slow_sorter(master, bldrs):
            bldrs.sort(lambda b1, b2 : cmp(b1.name, b2.name))
            d = defer.Deferred()
            reactor.callLater(0, d.callback, bldrs)
            def done(_):
                return _
            d.addCallback(done)
            return d
        self.brd.botmaster.prioritizeBuilders = slow_sorter

        self.addBuilders(builders)
        for bldr in builders:
            self.brd.maybeStartBuildsOn([bldr])
        def check(_):
            self.assertEqual(self.maybeStartBuild_calls, builders)
        self.quiet_deferred.addCallback(check)
        return self.quiet_deferred

    @compat.usesFlushLoggedErrors
    def test_maybeStartBuildsOn_exception(self):
        self.addBuilders(['bldr1'])

        def _callABuilder(n):
            # fail slowly, so that the activity loop doesn't go quiet too soon
            d = defer.Deferred()
            reactor.callLater(0,
                    d.errback, failure.Failure(RuntimeError("oh noes")))
            return d
        self.brd._callABuilder = _callABuilder

        self.brd.maybeStartBuildsOn(['bldr1'])
        def check(_):
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        self.quiet_deferred.addCallback(check)
        return self.quiet_deferred

    def test_maybeStartBuildsOn_collapsing(self):
        self.addBuilders(['bldr1', 'bldr2', 'bldr3'])
        self.brd.maybeStartBuildsOn(['bldr3'])
        self.brd.maybeStartBuildsOn(['bldr2', 'bldr1'])
        self.brd.maybeStartBuildsOn(['bldr4']) # should be ignored
        self.brd.maybeStartBuildsOn(['bldr2']) # already queued - ignored
        self.brd.maybeStartBuildsOn(['bldr3', 'bldr2'])
        def check(_):
            # bldr3 gets invoked twice, since it's considered to have started
            # already when the first call to maybeStartBuildsOn returns
            self.assertEqual(self.maybeStartBuild_calls,
                    ['bldr3', 'bldr1', 'bldr2', 'bldr3'])
        self.quiet_deferred.addCallback(check)
        return self.quiet_deferred

    def test_maybeStartBuildsOn_builders_missing(self):
        self.addBuilders(['bldr1', 'bldr2', 'bldr3'])
        self.brd.maybeStartBuildsOn(['bldr1', 'bldr2', 'bldr3'])
        # bldr1 is already run, so surreptitiously remove the other
        # two - nothing should crash, but the builders should not run
        self.removeBuilder('bldr2')
        self.removeBuilder('bldr3')
        def check(_):
            self.assertEqual(self.maybeStartBuild_calls, ['bldr1'])
        self.quiet_deferred.addCallback(check)
        return self.quiet_deferred

    def do_test_sortBuilders(self, prioritizeBuilders, oldestRequestTimes,
            expected, returnDeferred=False):
        self.addBuilders(oldestRequestTimes.keys())
        self.botmaster.prioritizeBuilders = prioritizeBuilders

        def mklambda(t): # work around variable-binding issues
            if returnDeferred:
                return lambda : defer.succeed(t)
            else:
                return lambda : t

        for n, t in oldestRequestTimes.iteritems():
            if t is not None:
                t = epoch2datetime(t)
            self.builders[n].getOldestRequestTime = mklambda(t)

        d = self.brd._sortBuilders(oldestRequestTimes.keys())
        def check(result):
            self.assertEqual(result, expected)
        d.addCallback(check)
        return d

    def test_sortBuilders_default_sync(self):
        return self.do_test_sortBuilders(None, # use the default sort
                dict(bldr1=777, bldr2=999, bldr3=888),
                ['bldr1', 'bldr3', 'bldr2'])

    def test_sortBuilders_default_asyn(self):
        return self.do_test_sortBuilders(None, # use the default sort
                dict(bldr1=777, bldr2=999, bldr3=888),
                ['bldr1', 'bldr3', 'bldr2'],
                returnDeferred=True)

    def test_sortBuilders_default_None(self):
        return self.do_test_sortBuilders(None, # use the default sort
                dict(bldr1=777, bldr2=None, bldr3=888),
                ['bldr1', 'bldr3', 'bldr2'])

    def test_sortBuilders_custom(self):
        def prioritizeBuilders(master, builders):
            self.assertIdentical(master, self.master)
            return sorted(builders, key=lambda b : b.name)

        return self.do_test_sortBuilders(prioritizeBuilders,
                dict(bldr1=1, bldr2=1, bldr3=1),
                ['bldr1', 'bldr2', 'bldr3'])

    def test_sortBuilders_custom_async(self):
        def prioritizeBuilders(master, builders):
            self.assertIdentical(master, self.master)
            return defer.succeed(sorted(builders, key=lambda b : b.name))

        return self.do_test_sortBuilders(prioritizeBuilders,
                dict(bldr1=1, bldr2=1, bldr3=1),
                ['bldr1', 'bldr2', 'bldr3'])

    @compat.usesFlushLoggedErrors
    def test_sortBuilders_custom_exception(self):
        self.addBuilders(['x', 'y'])
        def fail(m, b):
            raise RuntimeError("oh noes")
        self.botmaster.prioritizeBuilders = fail

        # expect to get the builders back in the same order in the event of an
        # exception
        d = self.brd._sortBuilders(['y', 'x'])
        def check(result):
            self.assertEqual(result, ['y', 'x'])

            # and expect the exception to be logged
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        d.addCallback(check)
        return d

    def test_stopService(self):
        # check that stopService waits for a builder run to complete, but does not
        # allow a subsequent run to start
        self.addBuilders(['A', 'B'])

        # patch the maybeStartBuild method for A to stop the service and wait a
        # beat, with some extra logging
        def msb_stopNow():
            self.maybeStartBuild_calls.append('A')
            stop_d = self.brd.stopService()
            stop_d.addCallback(lambda _ :
                    self.maybeStartBuild_calls.append('(stopped)'))

            d = defer.Deferred()
            def a_finished():
                self.maybeStartBuild_calls.append('A-finished')
                d.callback(None)
            reactor.callLater(0, a_finished)
            return d
        self.builders['A'].maybeStartBuild = msb_stopNow

        # start both builds; A should start and complete *before* the service stops,
        # and B should not run.
        self.brd.maybeStartBuildsOn(['A', 'B'])

        def check(_):
            self.assertEqual(self.maybeStartBuild_calls,
                    ['A', 'A-finished', '(stopped)'])
        self.quiet_deferred.addCallback(check)
        return self.quiet_deferred
