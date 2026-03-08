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

import random
from typing import TYPE_CHECKING
from typing import TypeVar

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot.test.util import fuzz
from buildbot.util import lru

if TYPE_CHECKING:
    from twisted.python.failure import Failure

    from buildbot.util.twisted import InlineCallbacksType

_T = TypeVar('_T')

# construct weakref-able objects for particular keys


def short(k: str) -> set[str]:
    return set([k.upper() * 3])


def long(k: str) -> set[str]:
    return set([k.upper() * 6])


def deferUntilLater(secs: float, result: _T = None) -> defer.Deferred[_T]:  # type: ignore[assignment]
    d: defer.Deferred[_T] = defer.Deferred()
    reactor.callLater(secs, d.callback, result)  # type: ignore[attr-defined]
    return d


class LRUCacheFuzzer(fuzz.FuzzTestCase):
    FUZZ_TIME = 60

    def setUp(self) -> None:
        lru.inv_failed = False

    def tearDown(self) -> None:
        self.assertFalse(lru.inv_failed, "invariant failed; see logs")
        if hasattr(self, 'lru'):
            log.msg(
                f"hits: {self.lru.hits}; misses: {self.lru.misses}; refhits: {self.lru.refhits}"
            )

    # tests

    @defer.inlineCallbacks
    def do_fuzz(self, endTime: float) -> InlineCallbacksType[None]:
        lru.inv_failed = False

        def delayed_miss_fn(key: int) -> defer.Deferred[set[int]]:
            return deferUntilLater(random.uniform(0.001, 0.002), set([key + 1000]))

        self.lru: lru.AsyncLRUCache[int, set[int]] = lru.AsyncLRUCache(delayed_miss_fn, 50)

        keys = list(range(250))
        errors: list[Failure] = []  # bail out early in the event of an error
        results = []  # keep references to (most) results

        # fire off as many requests as we can in one second, with lots of
        # overlap.
        while not errors and reactor.seconds() < endTime:  # type: ignore[attr-defined]
            key = random.choice(keys)

            d = self.lru.get(key)

            def check(result: set[int], key: int) -> None:
                self.assertEqual(result, set([key + 1000]))
                if random.uniform(0, 1.0) < 0.9:
                    results.append(result)
                    results[:-100] = []

            d.addCallback(check, key)

            @d.addErrback
            def eb(f: Failure) -> Failure:
                errors.append(f)
                return f  # unhandled error -> in the logs

            # give the reactor some time to process pending events
            if random.uniform(0, 1.0) < 0.5:
                yield deferUntilLater(0)

        # now wait until all of the pending calls have cleared, noting that
        # this method will be counted as one delayed call, in the current
        # implementation
        while len(reactor.getDelayedCalls()) > 1:  # type: ignore[attr-defined]
            # give the reactor some time to process pending events
            yield deferUntilLater(0.001)

        self.assertFalse(lru.inv_failed, "invariant failed; see logs")
        log.msg(f"hits: {self.lru.hits}; misses: {self.lru.misses}; refhits: {self.lru.refhits}")
