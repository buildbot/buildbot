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

from buildbot.data import exceptions
from buildbot.data import resultspec
from buildbot.data import workers
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import endpoint
from buildbot.test.util import interfaces

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType

testData = [
    fakedb.Builder(id=40, name='b1'),
    fakedb.Builder(id=41, name='b2'),
    fakedb.Master(id=13),
    fakedb.Master(id=14),
    fakedb.BuilderMaster(id=4013, builderid=40, masterid=13),
    fakedb.BuilderMaster(id=4014, builderid=40, masterid=14),
    fakedb.BuilderMaster(id=4113, builderid=41, masterid=13),
    fakedb.Worker(id=1, name='linux', info={}),
    fakedb.ConfiguredWorker(id=14013, workerid=1, buildermasterid=4013),
    fakedb.ConfiguredWorker(id=14014, workerid=1, buildermasterid=4014),
    fakedb.ConnectedWorker(id=113, masterid=13, workerid=1),
    fakedb.Worker(id=2, name='windows', info={"a": "b"}),
    fakedb.ConfiguredWorker(id=24013, workerid=2, buildermasterid=4013),
    fakedb.ConfiguredWorker(id=24014, workerid=2, buildermasterid=4014),
    fakedb.ConfiguredWorker(id=24113, workerid=2, buildermasterid=4113),
    fakedb.ConnectedWorker(id=214, masterid=14, workerid=2),
]


def configuredOnKey(worker: dict[str, Any]) -> tuple[int, int]:
    return (worker.get('masterid', 0), worker.get('builderid', 0))


def _filt(bs: dict[str, Any], builderid: int | None, masterid: int | None) -> dict[str, Any]:
    bs['connected_to'] = sorted([
        d for d in bs['connected_to'] if not masterid or masterid == d['masterid']
    ])
    bs['configured_on'] = sorted(
        [
            d
            for d in bs['configured_on']
            if (not masterid or masterid == d['masterid'])
            and (not builderid or builderid == d['builderid'])
        ],
        key=configuredOnKey,
    )
    return bs


def w1(builderid: int | None = None, masterid: int | None = None) -> dict[str, Any]:
    return _filt(
        {
            'workerid': 1,
            'name': 'linux',
            'workerinfo': {},
            'paused': False,
            'graceful': False,
            "pause_reason": None,
            'connected_to': [
                {'masterid': 13},
            ],
            'configured_on': sorted(
                [
                    {'builderid': 40, 'masterid': 13},
                    {'builderid': 40, 'masterid': 14},
                ],
                key=configuredOnKey,
            ),
        },
        builderid,
        masterid,
    )


def w2(builderid: int | None = None, masterid: int | None = None) -> dict[str, Any]:
    return _filt(
        {
            'workerid': 2,
            'name': 'windows',
            'workerinfo': {'a': 'b'},
            'paused': False,
            "pause_reason": None,
            'graceful': False,
            'connected_to': [
                {'masterid': 14},
            ],
            'configured_on': sorted(
                [
                    {'builderid': 40, 'masterid': 13},
                    {'builderid': 41, 'masterid': 13},
                    {'builderid': 40, 'masterid': 14},
                ],
                key=configuredOnKey,
            ),
        },
        builderid,
        masterid,
    )


class WorkerEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = workers.WorkerEndpoint
    resourceTypeClass = workers.Worker

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        yield self.setUpEndpoint()
        yield self.master.db.insert_test_data(testData)

    @defer.inlineCallbacks
    def test_get_existing(self) -> InlineCallbacksType[None]:
        worker = yield self.callGet(('workers', 2))

        self.validateData(worker)
        worker['configured_on'] = sorted(worker['configured_on'], key=configuredOnKey)
        self.assertEqual(worker, w2())

    @defer.inlineCallbacks
    def test_get_existing_name(self) -> InlineCallbacksType[None]:
        worker = yield self.callGet(('workers', 'linux'))

        self.validateData(worker)
        worker['configured_on'] = sorted(worker['configured_on'], key=configuredOnKey)
        self.assertEqual(worker, w1())

    @defer.inlineCallbacks
    def test_get_existing_masterid(self) -> InlineCallbacksType[None]:
        worker = yield self.callGet(('masters', 14, 'workers', 2))

        self.validateData(worker)
        worker['configured_on'] = sorted(worker['configured_on'], key=configuredOnKey)
        self.assertEqual(worker, w2(masterid=14))

    @defer.inlineCallbacks
    def test_get_existing_builderid(self) -> InlineCallbacksType[None]:
        worker = yield self.callGet(('builders', 40, 'workers', 2))

        self.validateData(worker)
        worker['configured_on'] = sorted(worker['configured_on'], key=configuredOnKey)
        self.assertEqual(worker, w2(builderid=40))

    @defer.inlineCallbacks
    def test_get_existing_masterid_builderid(self) -> InlineCallbacksType[None]:
        worker = yield self.callGet(('masters', 13, 'builders', 40, 'workers', 2))

        self.validateData(worker)
        worker['configured_on'] = sorted(worker['configured_on'], key=configuredOnKey)
        self.assertEqual(worker, w2(masterid=13, builderid=40))

    @defer.inlineCallbacks
    def test_get_missing(self) -> InlineCallbacksType[None]:
        worker = yield self.callGet(('workers', 99))

        self.assertEqual(worker, None)

    @defer.inlineCallbacks
    def test_set_worker_paused(self) -> InlineCallbacksType[None]:
        yield self.master.data.updates.set_worker_paused(2, True, "reason")
        worker = yield self.callGet(('workers', 2))
        self.validateData(worker)
        self.assertEqual(worker['paused'], True)
        self.assertEqual(worker["pause_reason"], "reason")

    @defer.inlineCallbacks
    def test_set_worker_graceful(self) -> InlineCallbacksType[None]:
        yield self.master.data.updates.set_worker_graceful(2, True)
        worker = yield self.callGet(('workers', 2))
        self.validateData(worker)
        self.assertEqual(worker['graceful'], True)

    @defer.inlineCallbacks
    def test_actions(self) -> InlineCallbacksType[None]:
        for action in ("stop", "pause", "unpause", "kill"):
            yield self.callControl(action, {}, ('masters', 13, 'builders', 40, 'workers', 2))
            self.master.mq.assertProductions([
                (('control', 'worker', '2', action), {'reason': 'no reason'})
            ])

    @defer.inlineCallbacks
    def test_bad_actions(self) -> InlineCallbacksType[None]:
        with self.assertRaises(exceptions.InvalidControlException):
            yield self.callControl("bad_action", {}, ('masters', 13, 'builders', 40, 'workers', 2))


class WorkersEndpoint(endpoint.EndpointMixin, unittest.TestCase):
    endpointClass = workers.WorkersEndpoint
    resourceTypeClass = workers.Worker

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        yield self.setUpEndpoint()
        yield self.master.db.insert_test_data(testData)

    @defer.inlineCallbacks
    def test_get(self) -> InlineCallbacksType[None]:
        workers = yield self.callGet(('workers',))

        for b in workers:
            self.validateData(b)
            b['configured_on'] = sorted(b['configured_on'], key=configuredOnKey)
        self.assertEqual(
            sorted(workers, key=configuredOnKey), sorted([w1(), w2()], key=configuredOnKey)
        )

    @defer.inlineCallbacks
    def test_get_masterid(self) -> InlineCallbacksType[None]:
        workers = yield self.callGet((
            'masters',
            '13',
            'workers',
        ))

        for b in workers:
            self.validateData(b)

        self.assertEqual(
            sorted(workers, key=configuredOnKey),
            sorted([w1(masterid=13), w2(masterid=13)], key=configuredOnKey),
        )

    @defer.inlineCallbacks
    def test_get_builderid(self) -> InlineCallbacksType[None]:
        workers = yield self.callGet((
            'builders',
            '41',
            'workers',
        ))

        for b in workers:
            self.validateData(b)

        self.assertEqual(
            sorted(workers, key=configuredOnKey), sorted([w2(builderid=41)], key=configuredOnKey)
        )

    @defer.inlineCallbacks
    def test_get_masterid_builderid(self) -> InlineCallbacksType[None]:
        workers = yield self.callGet((
            'masters',
            '13',
            'builders',
            '41',
            'workers',
        ))

        for b in workers:
            self.validateData(b)

        self.assertEqual(
            sorted(workers, key=configuredOnKey),
            sorted([w2(masterid=13, builderid=41)], key=configuredOnKey),
        )

    @defer.inlineCallbacks
    def test_set_worker_paused_find_by_paused(self) -> InlineCallbacksType[None]:
        yield self.master.data.updates.set_worker_paused(2, True, None)
        resultSpec = resultspec.OptimisedResultSpec(
            filters=[resultspec.Filter('paused', 'eq', [True])]
        )

        workers = yield self.callGet(('workers',), resultSpec=resultSpec)
        self.assertEqual(len(workers), 1)
        worker = workers[0]
        self.validateData(worker)
        self.assertEqual(worker['paused'], True)


class Worker(TestReactorMixin, interfaces.InterfaceTests, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantMq=True, wantDb=True, wantData=True)
        self.rtype = workers.Worker(self.master)
        yield self.master.db.insert_test_data([
            fakedb.Master(id=13),
            fakedb.Master(id=14),
        ])

    def test_signature_findWorkerId(self) -> None:
        @self.assertArgSpecMatches(
            self.master.data.updates.findWorkerId,  # fake
            self.rtype.findWorkerId,
        )  # real
        def findWorkerId(self: object, name: str) -> None:
            pass

    def test_signature_workerConfigured(self) -> None:
        @self.assertArgSpecMatches(
            self.master.data.updates.workerConfigured,  # fake
            self.rtype.workerConfigured,
        )  # real
        def workerConfigured(
            self: object, workerid: int, masterid: int, builderids: list[int]
        ) -> None:
            pass

    def test_signature_set_worker_paused(self) -> None:
        @self.assertArgSpecMatches(self.master.data.updates.set_worker_paused)
        def set_worker_paused(
            self: object, workerid: int, paused: bool, pause_reason: str | None = None
        ) -> None:
            pass

    def test_signature_set_worker_graceful(self) -> None:
        @self.assertArgSpecMatches(self.master.data.updates.set_worker_graceful)
        def set_worker_graceful(self: object, workerid: int, graceful: bool) -> None:
            pass

    def test_findWorkerId(self) -> None:
        # this just passes through to the db method, so test that
        rv = defer.succeed(None)
        self.master.db.workers.findWorkerId = mock.Mock(return_value=rv)
        self.assertIdentical(self.rtype.findWorkerId('foo'), rv)

    def test_findWorkerId_not_id(self) -> None:
        with self.assertRaises(ValueError):
            self.rtype.findWorkerId(b'foo')  # type: ignore[arg-type]
        with self.assertRaises(ValueError):
            self.rtype.findWorkerId('123/foo')
