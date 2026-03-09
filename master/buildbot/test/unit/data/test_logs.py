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
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.data import logs
from buildbot.db.logs import LogSlugExistsError
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces

if TYPE_CHECKING:
    from collections.abc import Callable

    from twisted.internet.defer import Deferred

    from buildbot.util.twisted import InlineCallbacksType


class LogEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = logs.LogEndpoint
    resourceTypeClass = logs.Log

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        yield self.setUpEndpoint()
        yield self.master.db.insert_test_data([
            fakedb.Builder(id=77, name='builder77'),
            fakedb.Master(id=88),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, builderid=77, buildsetid=8822),
            fakedb.Build(
                id=13, builderid=77, masterid=88, workerid=13, buildrequestid=82, number=3
            ),
            fakedb.Step(id=50, buildid=13, number=5, name='make'),
            fakedb.Log(id=60, stepid=50, name='stdio', slug='stdio', type='s'),
            fakedb.Log(id=61, stepid=50, name='errors', slug='errors', type='t'),
        ])

    @defer.inlineCallbacks
    def test_get_existing(self) -> InlineCallbacksType[None]:
        log = yield self.callGet(('logs', 60))
        self.validateData(log)
        self.assertEqual(
            log,
            {
                'logid': 60,
                'name': 'stdio',
                'slug': 'stdio',
                'stepid': 50,
                'complete': False,
                'num_lines': 0,
                'type': 's',
            },
        )

    @defer.inlineCallbacks
    def test_get_missing(self) -> InlineCallbacksType[None]:
        log = yield self.callGet(('logs', 62))
        self.assertEqual(log, None)

    @defer.inlineCallbacks
    def test_get_by_stepid(self) -> InlineCallbacksType[None]:
        log = yield self.callGet(('steps', 50, 'logs', 'errors'))
        self.validateData(log)
        self.assertEqual(log['name'], 'errors')

    @defer.inlineCallbacks
    def test_get_by_buildid(self) -> InlineCallbacksType[None]:
        log = yield self.callGet(('builds', 13, 'steps', 5, 'logs', 'errors'))
        self.validateData(log)
        self.assertEqual(log['name'], 'errors')

    @defer.inlineCallbacks
    def test_get_by_builder(self) -> InlineCallbacksType[None]:
        log = yield self.callGet(('builders', '77', 'builds', 3, 'steps', 5, 'logs', 'errors'))
        self.validateData(log)
        self.assertEqual(log['name'], 'errors')

    @defer.inlineCallbacks
    def test_get_by_builder_step_name(self) -> InlineCallbacksType[None]:
        log = yield self.callGet(('builders', '77', 'builds', 3, 'steps', 'make', 'logs', 'errors'))
        self.validateData(log)
        self.assertEqual(log['name'], 'errors')

    @defer.inlineCallbacks
    def test_get_by_buildername_step_name(self) -> InlineCallbacksType[None]:
        log = yield self.callGet((
            'builders',
            'builder77',
            'builds',
            3,
            'steps',
            'make',
            'logs',
            'errors',
        ))
        self.validateData(log)
        self.assertEqual(log['name'], 'errors')


class LogsEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = logs.LogsEndpoint
    resourceTypeClass = logs.Log

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        yield self.setUpEndpoint()
        yield self.master.db.insert_test_data([
            fakedb.Builder(id=77),
            fakedb.Master(id=88),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Buildset(id=8822),
            fakedb.BuildRequest(id=82, builderid=77, buildsetid=8822),
            fakedb.Build(
                id=13, builderid=77, masterid=88, workerid=13, buildrequestid=82, number=3
            ),
            fakedb.Step(id=50, buildid=13, number=9, name='make'),
            fakedb.Log(id=60, stepid=50, name='stdio', type='s'),
            fakedb.Log(id=61, stepid=50, name='errors', type='t'),
            fakedb.Step(id=51, buildid=13, number=10, name='make_install'),
            fakedb.Log(id=70, stepid=51, name='stdio', type='s'),
            fakedb.Log(id=71, stepid=51, name='results_html', type='h'),
            fakedb.Step(id=52, buildid=13, number=11, name='nothing'),
        ])

    @defer.inlineCallbacks
    def test_get_stepid(self) -> InlineCallbacksType[None]:
        logs = yield self.callGet(('steps', 50, 'logs'))

        for log in logs:
            self.validateData(log)

        self.assertEqual(sorted([b['name'] for b in logs]), ['errors', 'stdio'])

    @defer.inlineCallbacks
    def test_get_stepid_empty(self) -> InlineCallbacksType[None]:
        logs = yield self.callGet(('steps', 52, 'logs'))
        self.assertEqual(logs, [])

    @defer.inlineCallbacks
    def test_get_stepid_missing(self) -> InlineCallbacksType[None]:
        logs = yield self.callGet(('steps', 99, 'logs'))
        self.assertEqual(logs, [])

    @defer.inlineCallbacks
    def test_get_buildid_step_name(self) -> InlineCallbacksType[None]:
        logs = yield self.callGet(('builds', 13, 'steps', 'make_install', 'logs'))

        for log in logs:
            self.validateData(log)

        self.assertEqual(sorted([b['name'] for b in logs]), ['results_html', 'stdio'])

    @defer.inlineCallbacks
    def test_get_buildid_step_number(self) -> InlineCallbacksType[None]:
        logs = yield self.callGet(('builds', 13, 'steps', 10, 'logs'))

        for log in logs:
            self.validateData(log)

        self.assertEqual(sorted([b['name'] for b in logs]), ['results_html', 'stdio'])

    @defer.inlineCallbacks
    def test_get_builder_build_number_step_name(self) -> InlineCallbacksType[None]:
        logs = yield self.callGet(('builders', 77, 'builds', 3, 'steps', 'make', 'logs'))

        for log in logs:
            self.validateData(log)

        self.assertEqual(sorted([b['name'] for b in logs]), ['errors', 'stdio'])

    @defer.inlineCallbacks
    def test_get_builder_build_number_step_number(self) -> InlineCallbacksType[None]:
        logs = yield self.callGet(('builders', 77, 'builds', 3, 'steps', 10, 'logs'))

        for log in logs:
            self.validateData(log)

        self.assertEqual(sorted([b['name'] for b in logs]), ['results_html', 'stdio'])


class Log(TestReactorMixin, interfaces.InterfaceTests, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        self.rtype = logs.Log(self.master)

    @defer.inlineCallbacks
    def do_test_callthrough(
        self,
        dbMethodName: str,
        method: Callable[..., Deferred[Any]],
        exp_args: tuple[Any, ...] | None = None,
        exp_kwargs: dict[str, Any] | None = None,
        *args: Any,
        **kwargs: Any,
    ) -> InlineCallbacksType[None]:
        rv = (1, 2)
        m = mock.Mock(return_value=defer.succeed(rv))
        setattr(self.master.db.logs, dbMethodName, m)
        res = yield method(*args, **kwargs)
        self.assertIdentical(res, rv)
        m.assert_called_with(*(exp_args or args), **(exp_kwargs or kwargs))

    def test_signature_addLog(self) -> None:
        @self.assertArgSpecMatches(
            self.master.data.updates.addLog,  # fake
            self.rtype.addLog,
        )  # real
        def addLog(self: object, stepid: int, name: str, type: str) -> None:
            pass

    @defer.inlineCallbacks
    def test_addLog_uniquify(self) -> InlineCallbacksType[None]:
        tries = []

        @self.assertArgSpecMatches(self.master.db.logs.addLog)
        def addLog(stepid: int, name: str, slug: str, type: str) -> defer.Deferred[int]:
            tries.append((stepid, name, slug, type))
            if len(tries) < 3:
                return defer.fail(LogSlugExistsError())
            return defer.succeed(23)

        self.patch(self.master.db.logs, 'addLog', addLog)
        logid = yield self.rtype.addLog(stepid=13, name='foo', type='s')
        self.assertEqual(logid, 23)
        self.assertEqual(
            tries,
            [
                (13, 'foo', 'foo', 's'),
                (13, 'foo', 'foo_2', 's'),
                (13, 'foo', 'foo_3', 's'),
            ],
        )

    def test_signature_finishLog(self) -> None:
        @self.assertArgSpecMatches(
            self.master.data.updates.finishLog,  # fake
            self.rtype.finishLog,
        )  # real
        def finishLog(self: object, logid: int) -> None:
            pass

    def test_finishLog(self) -> None:
        self.do_test_callthrough('finishLog', self.rtype.finishLog, logid=10)

    def test_signature_compressLog(self) -> None:
        @self.assertArgSpecMatches(
            self.master.data.updates.compressLog,  # fake
            self.rtype.compressLog,
        )  # real
        def compressLog(self: object, logid: int) -> None:
            pass

    def test_compressLog(self) -> None:
        self.do_test_callthrough('compressLog', self.rtype.compressLog, logid=10)

    def test_signature_appendLog(self) -> None:
        @self.assertArgSpecMatches(
            self.master.data.updates.appendLog,  # fake
            self.rtype.appendLog,
        )  # real
        def appendLog(self: object, logid: int, content: str) -> None:
            pass

    def test_appendLog(self) -> None:
        self.do_test_callthrough('appendLog', self.rtype.appendLog, logid=10, content='foo\nbar\n')
