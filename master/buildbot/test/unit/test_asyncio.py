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

import asyncio

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import util
from buildbot.asyncio import as_deferred
from buildbot.test.reactor import TestReactorMixin


class TestAsyncioTestLoop(TestReactorMixin, unittest.TestCase):
    maxDiff = None

    def setUp(self):
        self.setup_test_reactor(use_asyncio=True)

    def test_coroutine_schedule(self):
        d1 = defer.Deferred()
        f1 = d1.asFuture(self.asyncio_loop)

        async def coro1():
            await f1

        f = asyncio.ensure_future(coro1())
        d1.callback(None)
        return defer.Deferred.fromFuture(f)

    @defer.inlineCallbacks
    def test_asyncio_gather(self):
        self.calls = 0

        async def coro1():
            await asyncio.sleep(1)
            self.calls += 1

        async def coro2():
            await asyncio.sleep(1)
            self.calls += 1

        @defer.inlineCallbacks
        def inlineCallbacks1():
            yield util.asyncSleep(1, self.reactor)
            self.calls += 1

        @defer.inlineCallbacks
        def inlineCallbacks2():
            yield util.asyncSleep(1, self.reactor)
            self.calls += 1

        async def main_coro():
            dl = []
            dl.append(coro1())
            dl.append(coro2())
            # We support directly yielding a deferred inside a asyncio coroutine
            # this needs a patch of Deferred.__await__ implemented in asyncio.py
            dl.append(inlineCallbacks1())
            dl.append(inlineCallbacks2().asFuture(self.asyncio_loop))
            await asyncio.gather(*dl)
            self.calls += 1

        f1 = main_coro()

        def advance():
            self.reactor.advance(1)
            if self.calls < 3:
                self.reactor.callLater(0, advance)
        yield advance()
        yield as_deferred(f1)

        self.assertEqual(self.calls, 5)

    @defer.inlineCallbacks
    def test_asyncio_threadsafe(self):
        f1 = asyncio.Future()

        async def coro():
            self.asyncio_loop.call_soon_threadsafe(f1.set_result, "ok")
            res = await f1
            return res

        res = yield as_deferred(coro())
        self.assertEqual(res, "ok")

    @defer.inlineCallbacks
    def test_asyncio_negative_call_at(self):
        res = yield as_deferred(defer.succeed("OK"))
        self.assertEqual(res, "OK")

    @defer.inlineCallbacks
    def test_asyncio_as_deferred_deferred(self):
        d = defer.Deferred()
        self.asyncio_loop.call_at(-1, d.callback, "OK")
        res = yield d
        self.assertEqual(res, "OK")

    @defer.inlineCallbacks
    def test_asyncio_as_deferred_default(self):
        res = yield as_deferred("OK")
        self.assertEqual(res, "OK")
