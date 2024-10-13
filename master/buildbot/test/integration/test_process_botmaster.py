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

from twisted.internet import defer

from buildbot.config import BuilderConfig
from buildbot.data import resultspec
from buildbot.process.factory import BuildFactory
from buildbot.process.results import SUCCESS
from buildbot.process.workerforbuilder import PingException
from buildbot.schedulers import triggerable
from buildbot.steps import trigger
from buildbot.test.fake.worker import WorkerController
from buildbot.test.util.integration import RunFakeMasterTestCase
from buildbot.util.twisted import async_to_deferred

if TYPE_CHECKING:
    from typing import Any
    from typing import Callable
    from typing import Coroutine
    from typing import TypeVar

    from typing_extensions import ParamSpec

    _T = TypeVar('_T')
    _P = ParamSpec('_P')


class Tests(RunFakeMasterTestCase):
    @defer.inlineCallbacks
    def do_terminates_ping_on_shutdown(self, quick_mode):
        """
        During shutdown we want to terminate any outstanding pings.
        """
        controller = WorkerController(self, 'local')

        config_dict = {
            'builders': [
                BuilderConfig(name="testy", workernames=['local'], factory=BuildFactory()),
            ],
            'workers': [controller.worker],
            'protocols': {'null': {}},
            'multiMaster': True,
        }
        yield self.setup_master(config_dict)
        builder_id = yield self.master.data.updates.findBuilderId('testy')

        yield controller.connect_worker()
        controller.sever_connection()
        yield self.create_build_request([builder_id])

        # give time for any delayed actions to complete
        self.reactor.advance(1)

        yield self.master.botmaster.cleanShutdown(quickMode=quick_mode, stopReactor=False)
        self.flushLoggedErrors(PingException)

    def test_terminates_ping_on_shutdown_quick_mode(self):
        return self.do_terminates_ping_on_shutdown(quick_mode=True)

    def test_terminates_ping_on_shutdown_slow_mode(self):
        return self.do_terminates_ping_on_shutdown(quick_mode=False)

    def _wait_step(self, wait_step: float = 0.1, timeout_seconds: float = 5.0):
        for _ in range(0, int(timeout_seconds * 1000), int(wait_step * 1000)):
            self.reactor.advance(wait_step)
            yield

    async def _query_until_result(
        self,
        fn: Callable[_P, Coroutine[Any, Any, _T]],
        *args: _P.args,
        **kwargs: _P.kwargs,
    ) -> _T:
        for _ in self._wait_step():
            result = await fn(*args, **kwargs)
            if result:
                return result
        self.fail('Fail to get result in appropriate timeout')

    @async_to_deferred
    async def test_shutdown_busy_with_child(self) -> None:
        """
        Test that clean shutdown complete correctly
        even when a running Build trigger another
        and wait for it's completion
        """

        parent_controller = WorkerController(self, 'parent_worker')
        child_controller = WorkerController(self, 'child_worker')

        config_dict = {
            'builders': [
                BuilderConfig(
                    name="parent",
                    workernames=[parent_controller.worker.name],
                    factory=BuildFactory([
                        trigger.Trigger(schedulerNames=['triggerable'], waitForFinish=True)
                    ]),
                ),
                BuilderConfig(
                    name="child", workernames=[child_controller.worker.name], factory=BuildFactory()
                ),
            ],
            'workers': [parent_controller.worker, child_controller.worker],
            'schedulers': [triggerable.Triggerable(name='triggerable', builderNames=['child'])],
            'protocols': {'null': {}},
            'multiMaster': True,
            'collapseRequests': False,
        }
        await self.setup_master(config_dict)

        parent_builder_id = await self.master.data.updates.findBuilderId('parent')
        child_builder_id = await self.master.data.updates.findBuilderId('child')

        await parent_controller.connect_worker()
        # Pause worker of Child builder so we know the build won't start before we start shutdown
        await child_controller.disconnect_worker()

        # Create a Child build without Parent so we can later make sure it was not executed
        _, first_child_brids = await self.create_build_request([child_builder_id])
        self.assertEqual(len(first_child_brids), 1)

        _, _parent_brids = await self.create_build_request([parent_builder_id])
        self.assertEqual(len(_parent_brids), 1)
        parent_brid = _parent_brids[parent_builder_id]

        # wait until Parent trigger it's Child build
        parent_buildid = (
            await self._query_until_result(
                self.master.data.get,
                ("builds",),
                filters=[resultspec.Filter('buildrequestid', 'eq', [parent_brid])],
            )
        )[0]['buildid']

        # now get the child_buildset
        child_buildsetid = (
            await self._query_until_result(
                self.master.data.get,
                ("buildsets",),
                filters=[resultspec.Filter('parent_buildid', 'eq', [parent_buildid])],
            )
        )[0]['bsid']

        # and finally, the child BuildReques
        child_buildrequest = (
            await self._query_until_result(
                self.master.data.get,
                ("buildrequests",),
                filters=[resultspec.Filter('buildsetid', 'eq', [child_buildsetid])],
            )
        )[0]

        # now we know the Parent's Child BuildRequest exists,
        # create a second Child without Parent for good measure
        _, second_child_brids = await self.create_build_request([child_builder_id])
        self.assertEqual(len(second_child_brids), 1)

        # Now start the clean shutdown
        shutdown_deferred: defer.Deferred[None] = self.master.botmaster.cleanShutdown(
            quickMode=False,
            stopReactor=False,
        )

        # Connect back Child worker so the build can happen
        await child_controller.connect_worker()

        # wait for the child request to be claimed, and completed
        for _ in self._wait_step():
            if child_buildrequest['claimed'] and child_buildrequest['complete']:
                break
            child_buildrequest = await self.master.data.get(
                ("buildrequests", child_buildrequest['buildrequestid']),
            )
            self.assertIsNotNone(child_buildrequest)
        self.assertEqual(child_buildrequest['results'], SUCCESS)

        # make sure parent-less BuildRequest weren't built
        first_child_request = await self.master.data.get(
            ("buildrequests", first_child_brids[child_builder_id]),
        )
        self.assertIsNotNone(first_child_request)
        self.assertFalse(first_child_request['claimed'])
        self.assertFalse(first_child_request['complete'])

        second_child_request = await self.master.data.get(
            ("buildrequests", second_child_brids[child_builder_id]),
        )
        self.assertIsNotNone(second_child_request)
        self.assertFalse(second_child_request['claimed'])
        self.assertFalse(second_child_request['complete'])

        # confirm Master shutdown
        await shutdown_deferred
        self.assertTrue(shutdown_deferred.called)
