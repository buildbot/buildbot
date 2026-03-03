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
from typing import cast

from parameterized import parameterized
from twisted.python.threadpool import ThreadPool
from twisted.trial import unittest

from buildbot.db.logs import _AsyncIterOnPool

if TYPE_CHECKING:
    from collections.abc import Generator

    from twisted.internet.interfaces import IReactorThreads


class _TestError(RuntimeError):
    pass


_PARAMS = [
    ('unlimited_wait', 0, True),
    ('single_wait', 1, True),
    ('multiple_wait', 5, True),
    ('unlimited_no_wait', 0, False),
    ('single_no_wait', 1, False),
    ('multiple_no_wait', 5, False),
]


class TestAsyncIterOnPoll(unittest.TestCase):
    def setUp(self) -> None:
        super().setUp()

        from twisted.internet import reactor  # noqa: PLC0415

        self.reactor = cast("IReactorThreads", reactor)

        self.thread_pool = ThreadPool(minthreads=1, maxthreads=1, name=f"{self.id()}-ThreadPool")
        self.thread_pool.start()

    def tearDown(self) -> None:
        self.thread_pool.stop()
        super().tearDown()

    @parameterized.expand(_PARAMS)
    async def test_exception_in_consumer(
        self, _name: str, max_backlog: int, wait_backlog: bool
    ) -> None:
        to_gen_count = 10

        def _generate_data() -> Generator[str, Any, None]:
            for _ in range(to_gen_count):
                yield "item"

        async def _iter(fail_on: int | None = None) -> None:
            idx = 0
            try:
                async with _AsyncIterOnPool(
                    generator_sync=_generate_data,
                    reactor=self.reactor,
                    provider_threadpool=self.thread_pool,
                    max_backlog=max_backlog,
                    wait_backlog_consumption=wait_backlog,
                ) as iterator:
                    async for _ in iterator:
                        idx += 1
                        if fail_on is not None and idx >= fail_on:
                            raise _TestError("simulate async consumer failure")
            except _TestError:
                pass

            if fail_on is not None:
                self.assertEqual(idx, fail_on)
            else:
                self.assertEqual(idx, to_gen_count)

        await _iter(fail_on=3)
        await _iter()

    @parameterized.expand(_PARAMS)
    async def test_exception_in_producer(
        self, _name: str, max_backlog: int, wait_backlog: bool
    ) -> None:
        to_gen_count = 10
        throw_on = 3

        def _generate_data() -> Generator[str, Any, None]:
            for idx in range(to_gen_count):
                if idx >= throw_on:
                    raise _TestError
                yield "item"

        idx = 0
        caught_inner = False
        caught_outer = False

        try:
            async with _AsyncIterOnPool(
                generator_sync=_generate_data,
                reactor=self.reactor,
                provider_threadpool=self.thread_pool,
                max_backlog=max_backlog,
                wait_backlog_consumption=wait_backlog,
            ) as iterator:
                try:
                    async for _ in iterator:
                        idx += 1
                except _TestError:
                    caught_inner = True
                    raise
        except _TestError:
            caught_outer = True

        self.assertEqual(idx, throw_on)
        self.assertTrue(caught_inner)
        self.assertTrue(caught_outer)

    @parameterized.expand(_PARAMS)
    async def test_incomplete_consumer(
        self, _name: str, max_backlog: int, wait_backlog: bool
    ) -> None:
        to_gen_count = 10

        def _generate_data() -> Generator[str, Any, None]:
            for _ in range(to_gen_count):
                yield "item"

        async def _iter(stop_on: int | None = None) -> None:
            idx = 0
            async with _AsyncIterOnPool(
                generator_sync=_generate_data,
                reactor=self.reactor,
                provider_threadpool=self.thread_pool,
                max_backlog=max_backlog,
                wait_backlog_consumption=wait_backlog,
            ) as iterator:
                async for _ in iterator:
                    idx += 1
                    if stop_on is not None and idx >= stop_on:
                        break

            if stop_on is not None:
                self.assertEqual(idx, stop_on)
            else:
                self.assertEqual(idx, to_gen_count)

        await _iter(stop_on=3)
        await _iter()
