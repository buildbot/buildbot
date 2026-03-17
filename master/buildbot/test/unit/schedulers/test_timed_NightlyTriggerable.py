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

from buildbot.process import properties
from buildbot.schedulers import timed
from buildbot.test import fakedb
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import scheduler
from buildbot.test.util.state import StateTestMixin

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class NightlyTriggerable(
    scheduler.SchedulerMixin, TestReactorMixin, StateTestMixin, unittest.TestCase
):
    SCHEDULERID = 327
    OBJECTID = 1327

    @defer.inlineCallbacks
    def makeScheduler(
        self, firstBuildDuration: int = 0, **kwargs: Any
    ) -> InlineCallbacksType[timed.NightlyTriggerable]:
        sched = yield self.attachScheduler(
            timed.NightlyTriggerable(**kwargs),
            self.OBJECTID,
            self.SCHEDULERID,
            overrideBuildsetMethods=True,
            createBuilderDB=True,
        )
        return sched

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        yield self.setUpScheduler()

    # utilities

    def assertBuildsetAdded(
        self,
        sourcestamps: list[dict[str, Any]] | None = None,
        properties: dict[str, tuple[Any, str]] | None = None,
    ) -> None:
        if sourcestamps is None:
            sourcestamps = []
        if properties is None:
            properties = {}
        properties['scheduler'] = ('test', 'Scheduler')
        self.assertEqual(
            self.addBuildsetCalls,
            [
                (
                    'addBuildsetForSourceStampsWithDefaults',
                    {
                        "builderNames": None,  # uses the default
                        "priority": None,
                        "properties": properties,
                        "reason": "The NightlyTriggerable scheduler named 'test' triggered this build",
                        "sourcestamps": sourcestamps,
                        "waited_for": False,
                    },
                ),
            ],
        )
        self.addBuildsetCalls = []

    def assertNoBuildsetAdded(self) -> None:
        self.assertEqual(self.addBuildsetCalls, [])

    # tests

    @defer.inlineCallbacks
    def test_constructor_no_reason(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(name='test', builderNames=['test'])
        yield sched.configureService()
        self.assertEqual(
            sched.reason, "The NightlyTriggerable scheduler named 'test' triggered this build"
        )

    @defer.inlineCallbacks
    def test_constructor_reason(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(
            name='test', builderNames=['test'], reason="hourlytriggerable"
        )
        yield sched.configureService()
        self.assertEqual(sched.reason, "hourlytriggerable")

    @defer.inlineCallbacks
    def test_constructor_month(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(name='test', builderNames=['test'], month='1')
        yield sched.configureService()
        self.assertEqual(sched.month, "1")

    @defer.inlineCallbacks
    def test_timer_noBuilds(self) -> InlineCallbacksType[None]:
        yield self.makeScheduler(name='test', builderNames=['test'], minute=[5])
        yield self.master.startService()

        self.reactor.advance(60 * 60)  # Run for 1h

        self.assertEqual(self.addBuildsetCalls, [])

    @defer.inlineCallbacks
    def test_timer_oneTrigger(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(
            name='test',
            builderNames=['test'],
            minute=[5],
            codebases={'cb': {'repository': 'annoying'}},
        )
        yield self.master.startService()

        sched.trigger(
            False,
            [
                {
                    "revision": 'myrev',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                    "codebase": 'cb',
                },
            ],
            set_props=None,
        )

        self.reactor.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(
            sourcestamps=[
                {
                    "codebase": 'cb',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                    "revision": 'myrev',
                },
            ]
        )

    @defer.inlineCallbacks
    def test_timer_twoTriggers(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(
            name='test',
            builderNames=['test'],
            minute=[5],
            codebases={'cb': {'repository': 'annoying'}},
        )

        yield self.master.startService()

        sched.trigger(
            False,
            [
                {
                    "codebase": 'cb',
                    "revision": 'myrev1',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                }
            ],
            set_props=None,
        )
        sched.trigger(
            False,
            [
                {
                    "codebase": 'cb',
                    "revision": 'myrev2',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                }
            ],
            set_props=None,
        )

        self.reactor.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(
            sourcestamps=[
                {
                    "codebase": 'cb',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                    # builds the second trigger's revision
                    "revision": 'myrev2',
                },
            ]
        )

    @defer.inlineCallbacks
    def test_timer_oneTrigger_then_noBuild(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(
            name='test',
            builderNames=['test'],
            minute=[5],
            codebases={'cb': {'repository': 'annoying'}},
        )

        yield self.master.startService()

        sched.trigger(
            False,
            [
                {
                    "codebase": 'cb',
                    "revision": 'myrev',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                }
            ],
            set_props=None,
        )

        self.reactor.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(
            sourcestamps=[
                {
                    "codebase": 'cb',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                    "revision": 'myrev',
                },
            ]
        )

        self.reactor.advance(60 * 60)  # Run for 1h

        # no trigger, so the second did not build
        self.assertNoBuildsetAdded()

    @defer.inlineCallbacks
    def test_timer_oneTriggers_then_oneTrigger(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(
            name='test',
            builderNames=['test'],
            minute=[5],
            codebases={'cb': {'repository': 'annoying'}},
        )

        yield self.master.startService()

        sched.trigger(
            False,
            [
                {
                    "codebase": 'cb',
                    "revision": 'myrev1',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                }
            ],
            set_props=None,
        )

        self.reactor.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(
            sourcestamps=[
                {
                    "codebase": 'cb',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                    "revision": 'myrev1',
                },
            ]
        )

        sched.trigger(
            False,
            [
                {
                    "codebase": 'cb',
                    "revision": 'myrev2',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                }
            ],
            set_props=None,
        )

        self.reactor.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(
            sourcestamps=[
                {
                    "codebase": 'cb',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                    "revision": 'myrev2',
                },
            ]
        )

    @defer.inlineCallbacks
    def test_savedTrigger(self) -> InlineCallbacksType[None]:
        yield self.makeScheduler(
            name='test',
            builderNames=['test'],
            minute=[5],
            codebases={'cb': {'repository': 'annoying'}},
        )

        value_json = (
            '[ [ {"codebase": "cb", "project": "p", "repository": "r", '
            '"branch": "br", "revision": "myrev"} ], {}, null, null ]'
        )

        yield self.master.db.insert_test_data([
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
            fakedb.ObjectState(
                objectid=self.SCHEDULERID, name='lastTrigger', value_json=value_json
            ),
        ])

        yield self.master.startService()

        self.reactor.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(
            sourcestamps=[
                {
                    "codebase": 'cb',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                    "revision": 'myrev',
                },
            ]
        )

    @defer.inlineCallbacks
    def test_savedTrigger_dict(self) -> InlineCallbacksType[None]:
        yield self.makeScheduler(
            name='test',
            builderNames=['test'],
            minute=[5],
            codebases={'cb': {'repository': 'annoying'}},
        )

        value_json = (
            '[ { "cb": {"codebase": "cb", "project": "p", "repository": "r", '
            '"branch": "br", "revision": "myrev"} }, {}, null, null ]'
        )
        yield self.master.db.insert_test_data([
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
            fakedb.ObjectState(
                objectid=self.SCHEDULERID, name='lastTrigger', value_json=value_json
            ),
        ])

        yield self.master.startService()

        self.reactor.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(
            sourcestamps=[
                {
                    "codebase": 'cb',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                    "revision": 'myrev',
                },
            ]
        )

    @defer.inlineCallbacks
    def test_saveTrigger(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(
            name='test',
            builderNames=['test'],
            minute=[5],
            codebases={'cb': {'repository': 'annoying'}},
        )
        yield self.master.db.insert_test_data([
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
        ])

        yield self.master.startService()

        _, d = sched.trigger(
            False,
            [
                {
                    "codebase": 'cb',
                    "revision": 'myrev',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                },
            ],
            set_props=None,
        )

        yield d
        yield self.assert_state(
            self.SCHEDULERID,
            lastTrigger=[
                [
                    {
                        "codebase": 'cb',
                        "revision": 'myrev',
                        "branch": 'br',
                        "project": 'p',
                        "repository": 'r',
                    },
                ],
                {},
                None,
                None,
            ],
        )

    @defer.inlineCallbacks
    def test_saveTrigger_noTrigger(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(
            name='test',
            builderNames=['test'],
            minute=[5],
            codebases={'cb': {'repository': 'annoying'}},
        )
        yield self.master.db.insert_test_data([
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
        ])

        yield self.master.startService()

        _, d = sched.trigger(
            False,
            [
                {
                    "codebase": 'cb',
                    "revision": 'myrev',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                },
            ],
            set_props=None,
        )

        self.reactor.advance(60 * 60)  # Run for 1h

        yield d
        yield self.assert_state(self.SCHEDULERID, lastTrigger=None)

    @defer.inlineCallbacks
    def test_triggerProperties(self) -> InlineCallbacksType[None]:
        sched = yield self.makeScheduler(
            name='test',
            builderNames=['test'],
            minute=[5],
            codebases={'cb': {'repository': 'annoying'}},
        )
        yield self.master.db.insert_test_data([
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
        ])

        yield self.master.startService()

        sched.trigger(
            False,
            [
                {
                    "codebase": 'cb',
                    "revision": 'myrev',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                },
            ],
            properties.Properties(testprop='test'),
        )

        yield self.assert_state(
            self.SCHEDULERID,
            lastTrigger=[
                [
                    {
                        "codebase": 'cb',
                        "revision": 'myrev',
                        "branch": 'br',
                        "project": 'p',
                        "repository": 'r',
                    },
                ],
                {'testprop': ['test', 'TEST']},
                None,
                None,
            ],
        )

        self.reactor.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(
            properties={"testprop": ('test', 'TEST')},
            sourcestamps=[
                {
                    "codebase": 'cb',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                    "revision": 'myrev',
                },
            ],
        )

    @defer.inlineCallbacks
    def test_savedProperties(self) -> InlineCallbacksType[None]:
        yield self.makeScheduler(
            name='test',
            builderNames=['test'],
            minute=[5],
            codebases={'cb': {'repository': 'annoying'}},
        )

        value_json = (
            '[ [ {"codebase": "cb", "project": "p", "repository": "r", '
            '"branch": "br", "revision": "myrev"} ], '
            '{"testprop": ["test", "TEST"]}, null, null ]'
        )
        yield self.master.db.insert_test_data([
            fakedb.Object(id=self.SCHEDULERID, name='test', class_name='NightlyTriggerable'),
            fakedb.ObjectState(
                objectid=self.SCHEDULERID, name='lastTrigger', value_json=value_json
            ),
        ])

        yield self.master.startService()

        self.reactor.advance(60 * 60)  # Run for 1h

        self.assertBuildsetAdded(
            properties={'testprop': ('test', 'TEST')},
            sourcestamps=[
                {
                    "codebase": 'cb',
                    "branch": 'br',
                    "project": 'p',
                    "repository": 'r',
                    "revision": 'myrev',
                },
            ],
        )
