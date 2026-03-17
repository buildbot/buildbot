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


from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.schedulers import timed
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import scheduler

if TYPE_CHECKING:
    from buildbot.process.properties import Properties
    from buildbot.util.twisted import InlineCallbacksType


class TestException(Exception):
    pass


class Periodic(scheduler.SchedulerMixin, TestReactorMixin, unittest.TestCase):
    OBJECTID = 23
    SCHEDULERID = 3

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        yield self.setUpScheduler()

    @defer.inlineCallbacks
    def makeScheduler(
        self,
        firstBuildDuration: int = 0,
        firstBuildError: bool = False,
        exp_branch: str | None = None,
        **kwargs: Any,
    ) -> InlineCallbacksType[timed.Periodic]:
        self.sched = sched = timed.Periodic(**kwargs)

        yield self.attachScheduler(self.sched, self.OBJECTID, self.SCHEDULERID)

        # keep track of builds in self.events
        self.events: list[str] = []

        def addBuildsetForSourceStampsWithDefaults(
            reason: str,
            sourcestamps: list[dict[str, Any]] | None = None,
            waited_for: bool = False,
            properties: Properties | None = None,
            builderNames: list[str] | None = None,
            **kw: Any,
        ) -> defer.Deferred[None]:
            self.assertIn('Periodic scheduler named', reason)
            # TODO: check branch
            isFirst = not self.events
            if self.reactor.seconds() == 0 and firstBuildError:
                raise TestException()
            self.events.append(f'B@{int(self.reactor.seconds())}')
            if isFirst and firstBuildDuration:
                d: defer.Deferred[None] = defer.Deferred()
                self.reactor.callLater(firstBuildDuration, d.callback, None)
                return d
            return defer.succeed(None)

        sched.addBuildsetForSourceStampsWithDefaults = addBuildsetForSourceStampsWithDefaults  # type: ignore[assignment,method-assign]

        # handle state locally
        self.state: dict[str, Any] = {}

        def getState(k: str, default: Any) -> defer.Deferred[Any]:
            return defer.succeed(self.state.get(k, default))

        sched.getState = getState  # type: ignore[method-assign]

        def setState(k: str, v: Any) -> defer.Deferred[None]:
            self.state[k] = v
            return defer.succeed(None)

        sched.setState = setState  # type: ignore[assignment,method-assign]

        return sched

    # tests

    def test_constructor_invalid(self) -> None:
        with self.assertRaises(config.ConfigErrors):
            timed.Periodic(name='test', builderNames=['test'], periodicBuildTimer=-2)

    @defer.inlineCallbacks
    def test_constructor_no_reason(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(name='test', builderNames=['test'], periodicBuildTimer=10)
        yield sched.configureService()
        self.assertEqual(sched.reason, "The Periodic scheduler named 'test' triggered this build")

    @defer.inlineCallbacks
    def test_constructor_reason(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(
            name='test', builderNames=['test'], periodicBuildTimer=10, reason="periodic"
        )
        yield sched.configureService()
        self.assertEqual(sched.reason, "periodic")

    @defer.inlineCallbacks
    def test_iterations_simple(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(name='test', builderNames=['test'], periodicBuildTimer=13)
        yield self.master.startService()

        sched.activate()
        self.reactor.advance(0)  # let it trigger the first build
        while self.reactor.seconds() < 30:
            self.reactor.advance(1)
        self.assertEqual(self.events, ['B@0', 'B@13', 'B@26'])
        self.assertEqual(self.state.get('last_build'), 26)

        yield sched.deactivate()

    @defer.inlineCallbacks
    def test_iterations_simple_branch(self) -> InlineCallbacksType[None]:
        yield self.makeScheduler(
            exp_branch='newfeature',
            name='test',
            builderNames=['test'],
            periodicBuildTimer=13,
            branch='newfeature',
        )

        yield self.master.startService()

        self.reactor.advance(0)  # let it trigger the first build
        while self.reactor.seconds() < 30:
            self.reactor.advance(1)
        self.assertEqual(self.events, ['B@0', 'B@13', 'B@26'])
        self.assertEqual(self.state.get('last_build'), 26)

    @defer.inlineCallbacks
    def test_iterations_long(self) -> InlineCallbacksType[None]:
        yield self.makeScheduler(
            name='test', builderNames=['test'], periodicBuildTimer=10, firstBuildDuration=15
        )  # takes a while to start a build

        yield self.master.startService()
        self.reactor.advance(0)  # let it trigger the first (longer) build
        while self.reactor.seconds() < 40:
            self.reactor.advance(1)
        self.assertEqual(self.events, ['B@0', 'B@15', 'B@25', 'B@35'])
        self.assertEqual(self.state.get('last_build'), 35)

    @defer.inlineCallbacks
    def test_start_build_error(self) -> InlineCallbacksType[None]:
        yield self.makeScheduler(
            name='test', builderNames=['test'], periodicBuildTimer=10, firstBuildError=True
        )  # error during first build start

        yield self.master.startService()
        self.reactor.advance(0)  # let it trigger the first (error) build
        while self.reactor.seconds() < 40:
            self.reactor.advance(1)
        self.assertEqual(self.events, ['B@10', 'B@20', 'B@30', 'B@40'])
        self.assertEqual(self.state.get('last_build'), 40)
        self.assertEqual(1, len(self.flushLoggedErrors(TestException)))

    @defer.inlineCallbacks
    def test_iterations_stop_while_starting_build(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(
            name='test', builderNames=['test'], periodicBuildTimer=13, firstBuildDuration=6
        )  # takes a while to start a build

        yield self.master.startService()
        self.reactor.advance(0)  # let it trigger the first (longer) build
        self.reactor.advance(3)  # get partway into that build

        d = sched.deactivate()  # begin stopping the service
        d.addCallback(lambda _: self.events.append(f'STOP@{int(self.reactor.seconds())}'))

        # run the clock out
        while self.reactor.seconds() < 40:
            self.reactor.advance(1)

        # note that the deactivate completes after the first build completes, and no
        # subsequent builds occur
        self.assertEqual(self.events, ['B@0', 'STOP@6'])
        self.assertEqual(self.state.get('last_build'), 0)

        yield d

    @defer.inlineCallbacks
    def test_iterations_with_initial_state(self) -> InlineCallbacksType[None]:
        yield self.makeScheduler(name='test', builderNames=['test'], periodicBuildTimer=13)
        # so next build should start in 6s
        self.state['last_build'] = self.reactor.seconds() - 7

        yield self.master.startService()
        self.reactor.advance(0)  # let it trigger the first build
        while self.reactor.seconds() < 30:
            self.reactor.advance(1)
        self.assertEqual(self.events, ['B@6', 'B@19'])
        self.assertEqual(self.state.get('last_build'), 19)

    @defer.inlineCallbacks
    def test_getNextBuildTime_None(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(name='test', builderNames=['test'], periodicBuildTimer=13)
        yield sched.configureService()
        # given None, build right away
        t = yield sched.getNextBuildTime(None)
        self.assertEqual(t, 0)

    @defer.inlineCallbacks
    def test_getNextBuildTime_given(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(name='test', builderNames=['test'], periodicBuildTimer=13)
        yield sched.configureService()
        # given a time, add the periodicBuildTimer to it
        t = yield sched.getNextBuildTime(20)
        self.assertEqual(t, 33)

    @defer.inlineCallbacks
    def test_enabled_callback(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(name='test', builderNames=['test'], periodicBuildTimer=13)
        yield self.master.startService()
        expectedValue = not sched.enabled
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, expectedValue)
        expectedValue = not sched.enabled
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, expectedValue)

        yield sched.deactivate()

    @defer.inlineCallbacks
    def test_disabled_activate(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(name='test', builderNames=['test'], periodicBuildTimer=13)
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        r = yield sched.activate()
        self.assertEqual(r, None)

    @defer.inlineCallbacks
    def test_disabled_deactivate(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(name='test', builderNames=['test'], periodicBuildTimer=13)
        yield self.master.startService()
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        yield sched.deactivate()

    @defer.inlineCallbacks
    def test_disabled_start_build(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(name='test', builderNames=['test'], periodicBuildTimer=13)
        yield sched._enabledCallback(None, {'enabled': not sched.enabled})
        self.assertEqual(sched.enabled, False)
        r = yield sched.startBuild()
        self.assertEqual(r, None)
