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

from buildbot.db import workers
from buildbot.test import fakedb
from buildbot.test.util import connector_component
from buildbot.test.util import interfaces
from buildbot.test.util import querylog


def workerKey(worker: workers.WorkerModel):
    return worker.id


def configuredOnKey(worker: workers.BuilderMasterModel):
    return (worker.builderid, worker.masterid)


class Tests(interfaces.InterfaceTests):
    # common sample data

    baseRows = [
        fakedb.Master(id=10, name='m10'),
        fakedb.Master(id=11, name='m11'),
        fakedb.Builder(id=20, name='a'),
        fakedb.Builder(id=21, name='b'),
        fakedb.Builder(id=22, name='c'),
        fakedb.Worker(id=30, name='zero'),
        fakedb.Worker(id=31, name='one'),
    ]

    multipleMasters = [
        fakedb.BuilderMaster(id=12, builderid=20, masterid=10),
        fakedb.BuilderMaster(id=13, builderid=21, masterid=10),
        fakedb.BuilderMaster(id=14, builderid=20, masterid=11),
        fakedb.BuilderMaster(id=15, builderid=22, masterid=11),
        fakedb.BuilderMaster(id=16, builderid=22, masterid=10),
        fakedb.ConfiguredWorker(id=3012, workerid=30, buildermasterid=12),
        fakedb.ConfiguredWorker(id=3013, workerid=30, buildermasterid=13),
        fakedb.ConfiguredWorker(id=3014, workerid=30, buildermasterid=14),
        fakedb.ConfiguredWorker(id=3114, workerid=31, buildermasterid=14),
        fakedb.ConfiguredWorker(id=3115, workerid=31, buildermasterid=15),
        fakedb.ConnectedWorker(id=3010, workerid=30, masterid=10),
        fakedb.ConnectedWorker(id=3111, workerid=31, masterid=11),
    ]

    # sample worker data, with id's avoiding the postgres id sequence

    BOGUS_NAME = 'bogus'

    W1_NAME = "w1"
    W1_ID = 100
    W1_INFO = {'a': 1}
    worker1_rows = [
        fakedb.Worker(id=W1_ID, name=W1_NAME, info=W1_INFO),
    ]

    W2_NAME = "w2"
    W2_ID = 200
    W2_INFO = {'a': 1, 'b': 2}
    worker2_rows = [
        fakedb.Worker(id=W2_ID, name=W2_NAME, info=W2_INFO),
    ]

    # tests

    def test_signature_findWorkerId(self):
        @self.assertArgSpecMatches(self.db.workers.findWorkerId)
        def findWorkerId(self, name):
            pass

    def test_signature_getWorker(self):
        @self.assertArgSpecMatches(self.db.workers.getWorker)
        def getWorker(self, workerid=None, name=None, masterid=None, builderid=None):
            pass

    def test_signature_getWorkers(self):
        @self.assertArgSpecMatches(self.db.workers.getWorkers)
        def getWorkers(self, masterid=None, builderid=None, paused=None, graceful=None):
            pass

    def test_signature_workerConnected(self):
        @self.assertArgSpecMatches(self.db.workers.workerConnected)
        def workerConnected(self, workerid, masterid, workerinfo):
            pass

    def test_signature_workerDisconnected(self):
        @self.assertArgSpecMatches(self.db.workers.workerDisconnected)
        def workerDisconnected(self, workerid, masterid):
            pass

    def test_signature_workerConfigured(self):
        @self.assertArgSpecMatches(self.db.workers.workerConfigured)
        def workerConfigured(self, workerid, masterid, builderids):
            pass

    def test_signature_deconfigureAllWorkersForMaster(self):
        @self.assertArgSpecMatches(self.db.workers.deconfigureAllWorkersForMaster)
        def deconfigureAllWorkersForMaster(self, masterid):
            pass

    def test_signature_set_worker_paused(self):
        @self.assertArgSpecMatches(self.db.workers.set_worker_paused)
        def set_worker_paused(self, workerid, paused, pause_reason=None):
            pass

    def test_signature_set_worker_graceful(self):
        @self.assertArgSpecMatches(self.db.workers.set_worker_graceful)
        def set_worker_graceful(self, workerid, graceful):
            pass

    async def test_findWorkerId_insert(self):
        id = await self.db.workers.findWorkerId(name="xyz")
        worker = await self.db.workers.getWorker(workerid=id)
        self.assertEqual(worker.name, 'xyz')
        self.assertEqual(worker.workerinfo, {})

    async def test_findWorkerId_existing(self):
        await self.insert_test_data(self.baseRows)
        id = await self.db.workers.findWorkerId(name="one")
        self.assertEqual(id, 31)

    async def test_getWorker_no_such(self):
        await self.insert_test_data(self.baseRows)
        workerdict = await self.db.workers.getWorker(workerid=99)
        self.assertEqual(workerdict, None)

    async def test_getWorker_by_name_no_such(self):
        await self.insert_test_data(self.baseRows)
        workerdict = await self.db.workers.getWorker(name='NOSUCH')
        self.assertEqual(workerdict, None)

    async def test_getWorker_not_configured(self):
        await self.insert_test_data(self.baseRows)
        workerdict = await self.db.workers.getWorker(workerid=30)
        self.assertIsInstance(workerdict, workers.WorkerModel)
        self.assertEqual(
            workerdict,
            workers.WorkerModel(
                id=30,
                name='zero',
                workerinfo={'a': 'b'},
                paused=False,
                pause_reason=None,
                graceful=False,
                connected_to=[],
                configured_on=[],
            ),
        )

    async def test_getWorker_connected_not_configured(self):
        await self.insert_test_data([
            *self.baseRows,
            # the worker is connected to this master, but not configured.
            # weird, but the DB should represent it.
            fakedb.Worker(id=32, name='two'),
            fakedb.ConnectedWorker(workerid=32, masterid=11),
        ])
        workerdict = await self.db.workers.getWorker(workerid=32)
        self.assertIsInstance(workerdict, workers.WorkerModel)
        self.assertEqual(
            workerdict,
            workers.WorkerModel(
                id=32,
                name='two',
                workerinfo={'a': 'b'},
                paused=False,
                pause_reason=None,
                graceful=False,
                connected_to=[11],
                configured_on=[],
            ),
        )

    async def test_getWorker_multiple_connections(self):
        await self.insert_test_data([
            *self.baseRows,
            # the worker is connected to two masters at once.
            # weird, but the DB should represent it.
            fakedb.Worker(id=32, name='two'),
            fakedb.ConnectedWorker(workerid=32, masterid=10),
            fakedb.ConnectedWorker(workerid=32, masterid=11),
            fakedb.BuilderMaster(id=24, builderid=20, masterid=10),
            fakedb.BuilderMaster(id=25, builderid=20, masterid=11),
            fakedb.ConfiguredWorker(workerid=32, buildermasterid=24),
            fakedb.ConfiguredWorker(workerid=32, buildermasterid=25),
        ])
        workerdict = await self.db.workers.getWorker(workerid=32)
        self.assertIsInstance(workerdict, workers.WorkerModel)
        self.assertEqual(
            workerdict,
            workers.WorkerModel(
                id=32,
                name='two',
                workerinfo={'a': 'b'},
                paused=False,
                pause_reason=None,
                graceful=False,
                connected_to=[10, 11],
                configured_on=[
                    workers.BuilderMasterModel(builderid=20, masterid=10),
                    workers.BuilderMasterModel(builderid=20, masterid=11),
                ],
            ),
        )

    async def test_getWorker_by_name_not_configured(self):
        await self.insert_test_data(self.baseRows)
        workerdict = await self.db.workers.getWorker(name='zero')
        self.assertIsInstance(workerdict, workers.WorkerModel)
        self.assertEqual(
            workerdict,
            workers.WorkerModel(
                id=30,
                name='zero',
                workerinfo={'a': 'b'},
                paused=False,
                pause_reason=None,
                graceful=False,
                connected_to=[],
                configured_on=[],
            ),
        )

    async def test_getWorker_not_connected(self):
        await self.insert_test_data([
            *self.baseRows,
            fakedb.BuilderMaster(id=12, builderid=20, masterid=10),
            fakedb.ConfiguredWorker(workerid=30, buildermasterid=12),
        ])
        workerdict = await self.db.workers.getWorker(workerid=30)
        self.assertIsInstance(workerdict, workers.WorkerModel)
        self.assertEqual(
            workerdict,
            workers.WorkerModel(
                id=30,
                name='zero',
                workerinfo={'a': 'b'},
                paused=False,
                pause_reason=None,
                graceful=False,
                configured_on=[workers.BuilderMasterModel(masterid=10, builderid=20)],
                connected_to=[],
            ),
        )

    async def test_getWorker_connected(self):
        await self.insert_test_data([
            *self.baseRows,
            fakedb.BuilderMaster(id=12, builderid=20, masterid=10),
            fakedb.ConfiguredWorker(workerid=30, buildermasterid=12),
            fakedb.ConnectedWorker(workerid=30, masterid=10),
        ])
        workerdict = await self.db.workers.getWorker(workerid=30)
        self.assertIsInstance(workerdict, workers.WorkerModel)
        self.assertEqual(
            workerdict,
            workers.WorkerModel(
                id=30,
                name='zero',
                workerinfo={'a': 'b'},
                paused=False,
                pause_reason=None,
                graceful=False,
                configured_on=[workers.BuilderMasterModel(masterid=10, builderid=20)],
                connected_to=[10],
            ),
        )

    async def test_getWorker_with_multiple_masters(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)
        workerdict = await self.db.workers.getWorker(workerid=30)
        self.assertIsInstance(workerdict, workers.WorkerModel)
        workerdict.configured_on = sorted(workerdict.configured_on, key=configuredOnKey)
        self.assertEqual(
            workerdict,
            workers.WorkerModel(
                id=30,
                name='zero',
                workerinfo={'a': 'b'},
                paused=False,
                pause_reason=None,
                graceful=False,
                configured_on=sorted(
                    [
                        workers.BuilderMasterModel(masterid=10, builderid=20),
                        workers.BuilderMasterModel(masterid=10, builderid=21),
                        workers.BuilderMasterModel(masterid=11, builderid=20),
                    ],
                    key=configuredOnKey,
                ),
                connected_to=[10],
            ),
        )

    async def test_getWorker_with_multiple_masters_builderid(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)
        workerdict = await self.db.workers.getWorker(workerid=30, builderid=20)
        self.assertIsInstance(workerdict, workers.WorkerModel)
        workerdict.configured_on = sorted(workerdict.configured_on, key=configuredOnKey)
        self.assertEqual(
            workerdict,
            workers.WorkerModel(
                id=30,
                name='zero',
                workerinfo={'a': 'b'},
                paused=False,
                pause_reason=None,
                graceful=False,
                configured_on=sorted(
                    [
                        workers.BuilderMasterModel(builderid=20, masterid=10),
                        workers.BuilderMasterModel(builderid=20, masterid=11),
                    ],
                    key=configuredOnKey,
                ),
                connected_to=[10],
            ),
        )

    async def test_getWorker_with_multiple_masters_masterid(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)
        workerdict = await self.db.workers.getWorker(workerid=30, masterid=11)
        self.assertIsInstance(workerdict, workers.WorkerModel)
        self.assertEqual(
            workerdict,
            workers.WorkerModel(
                id=30,
                name='zero',
                workerinfo={'a': 'b'},
                paused=False,
                pause_reason=None,
                graceful=False,
                configured_on=[
                    workers.BuilderMasterModel(builderid=20, masterid=11),
                ],
                connected_to=[],
            ),
        )

    async def test_getWorker_with_multiple_masters_builderid_masterid(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)
        workerdict = await self.db.workers.getWorker(workerid=30, builderid=20, masterid=11)
        self.assertIsInstance(workerdict, workers.WorkerModel)
        self.assertEqual(
            workerdict,
            workers.WorkerModel(
                id=30,
                name='zero',
                workerinfo={'a': 'b'},
                paused=False,
                pause_reason=None,
                graceful=False,
                configured_on=[
                    workers.BuilderMasterModel(builderid=20, masterid=11),
                ],
                connected_to=[],
            ),
        )

    async def test_getWorker_by_name_with_multiple_masters_builderid_masterid(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)
        workerdict = await self.db.workers.getWorker(name='zero', builderid=20, masterid=11)
        self.assertIsInstance(workerdict, workers.WorkerModel)
        self.assertEqual(
            workerdict,
            workers.WorkerModel(
                id=30,
                name='zero',
                workerinfo={'a': 'b'},
                paused=False,
                pause_reason=None,
                graceful=False,
                configured_on=[
                    workers.BuilderMasterModel(masterid=11, builderid=20),
                ],
                connected_to=[],
            ),
        )

    async def test_getWorkers_no_config(self):
        await self.insert_test_data(self.baseRows)
        workerdicts = await self.db.workers.getWorkers()

        for workerdict in workerdicts:
            self.assertIsInstance(workerdict, workers.WorkerModel)

        self.assertEqual(
            sorted(workerdicts, key=workerKey),
            sorted(
                [
                    workers.WorkerModel(
                        id=30,
                        name='zero',
                        workerinfo={'a': 'b'},
                        paused=False,
                        pause_reason=None,
                        graceful=False,
                        configured_on=[],
                        connected_to=[],
                    ),
                    workers.WorkerModel(
                        id=31,
                        name='one',
                        workerinfo={'a': 'b'},
                        paused=False,
                        pause_reason=None,
                        graceful=False,
                        configured_on=[],
                        connected_to=[],
                    ),
                ],
                key=workerKey,
            ),
        )

    async def test_getWorkers_with_config(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)
        workerdicts = await self.db.workers.getWorkers()
        for workerdict in workerdicts:
            self.assertIsInstance(workerdict, workers.WorkerModel)
            workerdict.configured_on = sorted(workerdict.configured_on, key=configuredOnKey)
        self.assertEqual(
            sorted(workerdicts, key=workerKey),
            sorted(
                [
                    workers.WorkerModel(
                        id=30,
                        name='zero',
                        workerinfo={'a': 'b'},
                        paused=False,
                        pause_reason=None,
                        graceful=False,
                        configured_on=sorted(
                            [
                                workers.BuilderMasterModel(builderid=20, masterid=10),
                                workers.BuilderMasterModel(builderid=21, masterid=10),
                                workers.BuilderMasterModel(builderid=20, masterid=11),
                            ],
                            key=configuredOnKey,
                        ),
                        connected_to=[10],
                    ),
                    workers.WorkerModel(
                        id=31,
                        name='one',
                        workerinfo={'a': 'b'},
                        paused=False,
                        pause_reason=None,
                        graceful=False,
                        configured_on=sorted(
                            [
                                workers.BuilderMasterModel(builderid=20, masterid=11),
                                workers.BuilderMasterModel(builderid=22, masterid=11),
                            ],
                            key=configuredOnKey,
                        ),
                        connected_to=[11],
                    ),
                ],
                key=workerKey,
            ),
        )

    async def test_getWorkers_empty(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)
        workerdicts = await self.db.workers.getWorkers(masterid=11, builderid=21)
        for workerdict in workerdicts:
            self.assertIsInstance(workerdict, workers.WorkerModel)
            workerdict.configured_on = sorted(workerdict.configured_on, key=configuredOnKey)
        self.assertEqual(sorted(workerdicts, key=workerKey), [])

    async def test_getWorkers_with_config_builderid(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)
        workerdicts = await self.db.workers.getWorkers(builderid=20)
        for workerdict in workerdicts:
            self.assertIsInstance(workerdict, workers.WorkerModel)
            workerdict.configured_on = sorted(workerdict.configured_on, key=configuredOnKey)
        self.assertEqual(
            sorted(workerdicts, key=workerKey),
            sorted(
                [
                    workers.WorkerModel(
                        id=30,
                        name='zero',
                        workerinfo={'a': 'b'},
                        paused=False,
                        pause_reason=None,
                        graceful=False,
                        configured_on=sorted(
                            [
                                workers.BuilderMasterModel(builderid=20, masterid=10),
                                workers.BuilderMasterModel(builderid=20, masterid=11),
                            ],
                            key=configuredOnKey,
                        ),
                        connected_to=[10],
                    ),
                    workers.WorkerModel(
                        id=31,
                        name='one',
                        workerinfo={'a': 'b'},
                        paused=False,
                        pause_reason=None,
                        graceful=False,
                        configured_on=sorted(
                            [
                                workers.BuilderMasterModel(builderid=20, masterid=11),
                            ],
                            key=configuredOnKey,
                        ),
                        connected_to=[11],
                    ),
                ],
                key=workerKey,
            ),
        )

    async def test_getWorkers_with_config_masterid_10(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)
        workerdicts = await self.db.workers.getWorkers(masterid=10)
        for workerdict in workerdicts:
            self.assertIsInstance(workerdict, workers.WorkerModel)
            workerdict.configured_on = sorted(workerdict.configured_on, key=configuredOnKey)
        self.assertEqual(
            sorted(workerdicts, key=workerKey),
            sorted(
                [
                    workers.WorkerModel(
                        id=30,
                        name='zero',
                        workerinfo={'a': 'b'},
                        paused=False,
                        pause_reason=None,
                        graceful=False,
                        configured_on=sorted(
                            [
                                workers.BuilderMasterModel(builderid=20, masterid=10),
                                workers.BuilderMasterModel(builderid=21, masterid=10),
                            ],
                            key=configuredOnKey,
                        ),
                        connected_to=[10],
                    ),
                ],
                key=workerKey,
            ),
        )

    async def test_getWorkers_with_config_masterid_11(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)
        workerdicts = await self.db.workers.getWorkers(masterid=11)
        for workerdict in workerdicts:
            self.assertIsInstance(workerdict, workers.WorkerModel)
            workerdict.configured_on = sorted(workerdict.configured_on, key=configuredOnKey)
        self.assertEqual(
            sorted(workerdicts, key=workerKey),
            sorted(
                [
                    workers.WorkerModel(
                        id=30,
                        name='zero',
                        workerinfo={'a': 'b'},
                        paused=False,
                        pause_reason=None,
                        graceful=False,
                        configured_on=sorted(
                            [
                                workers.BuilderMasterModel(builderid=20, masterid=11),
                            ],
                            key=configuredOnKey,
                        ),
                        connected_to=[],
                    ),
                    workers.WorkerModel(
                        id=31,
                        name='one',
                        workerinfo={'a': 'b'},
                        paused=False,
                        pause_reason=None,
                        graceful=False,
                        configured_on=sorted(
                            [
                                workers.BuilderMasterModel(builderid=20, masterid=11),
                                workers.BuilderMasterModel(builderid=22, masterid=11),
                            ],
                            key=configuredOnKey,
                        ),
                        connected_to=[11],
                    ),
                ],
                key=workerKey,
            ),
        )

    async def test_getWorkers_with_config_masterid_11_builderid_22(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)
        workerdicts = await self.db.workers.getWorkers(masterid=11, builderid=22)
        for workerdict in workerdicts:
            self.assertIsInstance(workerdict, workers.WorkerModel)
            workerdict.configured_on = sorted(workerdict.configured_on, key=configuredOnKey)
        self.assertEqual(
            sorted(workerdicts, key=workerKey),
            sorted(
                [
                    workers.WorkerModel(
                        id=31,
                        name='one',
                        workerinfo={'a': 'b'},
                        paused=False,
                        pause_reason=None,
                        graceful=False,
                        configured_on=sorted(
                            [
                                workers.BuilderMasterModel(builderid=22, masterid=11),
                            ],
                            key=configuredOnKey,
                        ),
                        connected_to=[11],
                    ),
                ],
                key=workerKey,
            ),
        )

    async def test_getWorkers_with_paused(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)
        await self.db.workers.set_worker_paused(31, paused=True, pause_reason="reason")
        await self.db.workers.set_worker_graceful(31, graceful=False)
        workerdicts = await self.db.workers.getWorkers(paused=True)
        for workerdict in workerdicts:
            self.assertIsInstance(workerdict, workers.WorkerModel)
            workerdict.configured_on = []
        self.assertEqual(
            workerdicts,
            [
                workers.WorkerModel(
                    id=31,
                    name='one',
                    workerinfo={'a': 'b'},
                    paused=True,
                    pause_reason="reason",
                    graceful=False,
                    configured_on=[],
                    connected_to=[11],
                ),
            ],
        )

    async def test_getWorkers_with_graceful(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)
        await self.db.workers.set_worker_paused(31, paused=False)
        await self.db.workers.set_worker_graceful(31, graceful=True)
        workerdicts = await self.db.workers.getWorkers(graceful=True)
        for workerdict in workerdicts:
            self.assertIsInstance(workerdict, workers.WorkerModel)
            workerdict.configured_on = []
        self.assertEqual(
            workerdicts,
            [
                workers.WorkerModel(
                    id=31,
                    name='one',
                    workerinfo={'a': 'b'},
                    paused=False,
                    pause_reason=None,
                    graceful=True,
                    configured_on=[],
                    connected_to=[11],
                ),
            ],
        )

    async def test_workerConnected_existing(self):
        await self.insert_test_data(self.baseRows + self.worker1_rows)

        NEW_INFO = {'other': [1, 2, 3]}

        await self.db.workers.workerConnected(workerid=self.W1_ID, masterid=11, workerinfo=NEW_INFO)

        w = await self.db.workers.getWorker(self.W1_ID)
        self.assertEqual(
            w,
            workers.WorkerModel(
                id=self.W1_ID,
                name=self.W1_NAME,
                workerinfo=NEW_INFO,
                paused=False,
                pause_reason=None,
                graceful=False,
                configured_on=[],
                connected_to=[11],
            ),
        )

    async def test_workerConnected_already_connected(self):
        await self.insert_test_data(
            self.baseRows
            + self.worker1_rows
            + [
                fakedb.ConnectedWorker(id=888, workerid=self.W1_ID, masterid=11),
            ]
        )
        await self.db.workers.workerConnected(workerid=self.W1_ID, masterid=11, workerinfo={})

        w = await self.db.workers.getWorker(self.W1_ID)
        self.assertEqual(w.connected_to, [11])

    async def test_workerDisconnected(self):
        await self.insert_test_data(
            self.baseRows
            + self.worker1_rows
            + [
                fakedb.ConnectedWorker(id=888, workerid=self.W1_ID, masterid=10),
                fakedb.ConnectedWorker(id=889, workerid=self.W1_ID, masterid=11),
            ]
        )
        await self.db.workers.workerDisconnected(workerid=self.W1_ID, masterid=11)

        w = await self.db.workers.getWorker(self.W1_ID)
        self.assertEqual(w.connected_to, [10])

    async def test_workerDisconnected_already_disconnected(self):
        await self.insert_test_data(self.baseRows + self.worker1_rows)
        await self.db.workers.workerDisconnected(workerid=self.W1_ID, masterid=11)

        w = await self.db.workers.getWorker(self.W1_ID)
        self.assertEqual(w.connected_to, [])

    async def test_set_worker_paused_existing(self):
        await self.insert_test_data(self.baseRows + self.worker1_rows)

        await self.db.workers.set_worker_paused(self.W1_ID, False, None)

        w = await self.db.workers.getWorker(self.W1_ID)
        self.assertEqual(
            w,
            workers.WorkerModel(
                id=self.W1_ID,
                name=self.W1_NAME,
                workerinfo=self.W1_INFO,
                paused=False,
                pause_reason=None,
                graceful=False,
                configured_on=[],
                connected_to=[],
            ),
        )

        await self.db.workers.set_worker_paused(self.W1_ID, True, "reason")

        w = await self.db.workers.getWorker(self.W1_ID)
        self.assertEqual(
            w,
            workers.WorkerModel(
                id=self.W1_ID,
                name=self.W1_NAME,
                workerinfo=self.W1_INFO,
                paused=True,
                pause_reason="reason",
                graceful=False,
                configured_on=[],
                connected_to=[],
            ),
        )

    async def test_set_worker_graceful_existing(self):
        await self.insert_test_data(self.baseRows + self.worker1_rows)

        await self.db.workers.set_worker_graceful(self.W1_ID, False)

        w = await self.db.workers.getWorker(self.W1_ID)
        self.assertEqual(
            w,
            workers.WorkerModel(
                id=self.W1_ID,
                name=self.W1_NAME,
                workerinfo=self.W1_INFO,
                paused=False,
                pause_reason=None,
                graceful=False,
                configured_on=[],
                connected_to=[],
            ),
        )

        await self.db.workers.set_worker_graceful(self.W1_ID, True)

        w = await self.db.workers.getWorker(self.W1_ID)
        self.assertEqual(
            w,
            workers.WorkerModel(
                id=self.W1_ID,
                name=self.W1_NAME,
                workerinfo=self.W1_INFO,
                paused=False,
                pause_reason=None,
                graceful=True,
                configured_on=[],
                connected_to=[],
            ),
        )

    async def test_workerConfigured(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        await self.db.workers.deconfigureAllWorkersForMaster(masterid=10)

        await self.db.workers.workerConfigured(workerid=30, masterid=10, builderids=[20, 22])

        w = await self.db.workers.getWorker(30)
        self.assertEqual(
            sorted(w.configured_on, key=configuredOnKey),
            sorted(
                [
                    workers.BuilderMasterModel(builderid=20, masterid=11),
                    workers.BuilderMasterModel(builderid=20, masterid=10),
                    workers.BuilderMasterModel(builderid=22, masterid=10),
                ],
                key=configuredOnKey,
            ),
        )

    async def test_workerConfiguredTwice(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        await self.db.workers.deconfigureAllWorkersForMaster(masterid=10)

        await self.db.workers.workerConfigured(workerid=30, masterid=10, builderids=[20, 22])

        # configure again (should eat the duplicate insertion errors)
        await self.db.workers.workerConfigured(workerid=30, masterid=10, builderids=[20, 21, 22])

        w = await self.db.workers.getWorker(30)
        x1 = sorted(w.configured_on, key=configuredOnKey)
        x2 = sorted(
            [
                workers.BuilderMasterModel(builderid=20, masterid=11),
                workers.BuilderMasterModel(builderid=20, masterid=10),
                workers.BuilderMasterModel(builderid=21, masterid=10),
                workers.BuilderMasterModel(builderid=22, masterid=10),
            ],
            key=configuredOnKey,
        )
        self.assertEqual(x1, x2)

    async def test_workerReConfigured(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        await self.db.workers.workerConfigured(workerid=30, masterid=10, builderids=[20, 22])

        w = await self.db.workers.getWorker(30)
        w.configured_on = sorted(w.configured_on, key=configuredOnKey)
        self.assertEqual(
            w.configured_on,
            sorted(
                [
                    workers.BuilderMasterModel(builderid=20, masterid=11),
                    workers.BuilderMasterModel(builderid=20, masterid=10),
                    workers.BuilderMasterModel(builderid=22, masterid=10),
                ],
                key=configuredOnKey,
            ),
        )

    async def test_workerReConfigured_should_not_affect_other_worker(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)

        # should remove all the builders in master 11
        await self.db.workers.workerConfigured(workerid=30, masterid=11, builderids=[])

        w = await self.db.workers.getWorker(30)
        x1 = sorted(w.configured_on, key=configuredOnKey)
        x2 = sorted(
            [
                workers.BuilderMasterModel(builderid=20, masterid=10),
                workers.BuilderMasterModel(builderid=21, masterid=10),
            ],
            key=configuredOnKey,
        )
        self.assertEqual(x1, x2)

        # ensure worker 31 is not affected (see GitHub issue#3392)
        w = await self.db.workers.getWorker(31)
        x1 = sorted(w.configured_on, key=configuredOnKey)
        x2 = sorted(
            [
                workers.BuilderMasterModel(builderid=20, masterid=11),
                workers.BuilderMasterModel(builderid=22, masterid=11),
            ],
            key=configuredOnKey,
        )
        self.assertEqual(x1, x2)

    async def test_workerUnconfigured(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)

        # should remove all builders from master 10
        await self.db.workers.workerConfigured(workerid=30, masterid=10, builderids=[])

        w = await self.db.workers.getWorker(30)
        w.configured_on = sorted(w.configured_on, key=configuredOnKey)
        expected = sorted(
            [workers.BuilderMasterModel(builderid=20, masterid=11)], key=configuredOnKey
        )
        self.assertEqual(w.configured_on, expected)

    async def test_nothingConfigured(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)

        # should remove builder 21, and add 22
        await self.db.workers.deconfigureAllWorkersForMaster(masterid=10)
        await self.db.workers.workerConfigured(workerid=30, masterid=10, builderids=[])

        # should only keep builder for master 11
        w = await self.db.workers.getWorker(30)
        self.assertEqual(
            sorted(w.configured_on), sorted([workers.BuilderMasterModel(builderid=20, masterid=11)])
        )

    async def test_deconfiguredAllWorkers(self):
        await self.insert_test_data(self.baseRows + self.multipleMasters)

        res = await self.db.workers.getWorkers(masterid=11)
        self.assertEqual(len(res), 2)

        # should remove all worker configured for masterid 11
        await self.db.workers.deconfigureAllWorkersForMaster(masterid=11)

        res = await self.db.workers.getWorkers(masterid=11)
        self.assertEqual(len(res), 0)


class RealTests(Tests):
    # tests that only "real" implementations will pass
    pass


class TestFakeDB(unittest.TestCase, connector_component.FakeConnectorComponentMixin, Tests):
    async def setUp(self):
        await self.setUpConnectorComponent()


class TestRealDB(
    unittest.TestCase,
    connector_component.ConnectorComponentMixin,
    RealTests,
    querylog.SqliteMaxVariableMixin,
):
    async def setUp(self):
        await self.setUpConnectorComponent(
            table_names=[
                'workers',
                'masters',
                'projects',
                'builders',
                'builder_masters',
                'connected_workers',
                'configured_workers',
            ]
        )

        self.db.workers = workers.WorkersConnectorComponent(self.db)

    async def test_workerConfiguredMany(self):
        manyWorkers = (
            [
                fakedb.BuilderMaster(id=1000, builderid=20, masterid=10),
            ]
            + [fakedb.Worker(id=50 + n, name='zero' + str(n)) for n in range(1000)]
            + [
                fakedb.ConfiguredWorker(id=n + 3000, workerid=50 + n, buildermasterid=1000)
                for n in range(1000)
            ]
        )
        await self.insert_test_data(self.baseRows + manyWorkers)

        # should successfully remove all ConfiguredWorker rows
        with self.assertNoMaxVariables():
            await self.db.workers.deconfigureAllWorkersForMaster(masterid=10)

        w = await self.db.workers.getWorker(30)
        self.assertEqual(sorted(w.configured_on), [])

    async def test_workerConfiguredManyBuilders(self):
        manyWorkers = (
            [fakedb.Builder(id=100 + n, name='a' + str(n)) for n in range(1000)]
            + [fakedb.Worker(id=50 + n, name='zero' + str(n)) for n in range(2000)]
            + [
                fakedb.BuilderMaster(id=1000 + n, builderid=100 + n, masterid=10)
                for n in range(1000)
            ]
            + [
                fakedb.ConfiguredWorker(
                    id=n + 3000, workerid=50 + n, buildermasterid=int(1000 + n / 2)
                )
                for n in range(2000)
            ]
        )
        await self.insert_test_data(self.baseRows + manyWorkers)

        # should successfully remove all ConfiguredWorker rows
        with self.assertNoMaxVariables():
            await self.db.workers.deconfigureAllWorkersForMaster(masterid=10)
        w = await self.db.workers.getWorker(30)
        self.assertEqual(sorted(w.configured_on), [])

    def tearDown(self):
        return self.tearDownConnectorComponent()
