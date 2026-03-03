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

from collections import defaultdict
from collections import deque
from itertools import filterfalse
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import Generic
from typing import TypeVar
from weakref import WeakValueDictionary

from twisted.internet import defer
from twisted.python import log

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from twisted.python.failure import Failure
    from typing_extensions import Concatenate


_KT = TypeVar('_KT')
_KV = TypeVar('_KV')


class LRUCache(Generic[_KT, _KV]):
    """
    A least-recently-used cache, with a fixed maximum size.

    See buildbot manual for more information.
    """

    __slots__ = (
        'max_size max_queue miss_fn queue cache weakrefs refcount hits refhits misses'.split()
    )
    sentinel = object()
    QUEUE_SIZE_FACTOR = 10

    def __init__(self, miss_fn: Callable[Concatenate[_KT, ...], _KV], max_size: int = 50) -> None:
        self.max_size = max_size
        self.max_queue = max_size * self.QUEUE_SIZE_FACTOR
        self.queue: deque[_KT] = deque()
        self.cache: dict[_KT, _KV] = {}
        self.weakrefs: WeakValueDictionary[_KT, _KV] = WeakValueDictionary()
        self.hits = self.misses = self.refhits = 0
        self.refcount: defaultdict[_KT, int] = defaultdict(lambda: 0)
        self.miss_fn = miss_fn

    def put(self, key: _KT, value: _KV) -> None:
        cached = key in self.cache or key in self.weakrefs
        self.cache[key] = value
        self.weakrefs[key] = value
        self._ref_key(key)
        if not cached:
            self._purge()

    def get(self, key: _KT, **miss_fn_kwargs: Any) -> _KV:
        try:
            return self._get_hit(key)
        except KeyError:
            pass

        self.misses += 1

        result = self.miss_fn(key, **miss_fn_kwargs)
        if result is not None:
            self.cache[key] = result
            self.weakrefs[key] = result
            self._ref_key(key)
            self._purge()

        return result

    def keys(self) -> list[_KT]:
        return list(self.cache)

    def set_max_size(self, max_size: int) -> None:
        if self.max_size == max_size:
            return

        self.max_size = max_size
        self.max_queue = max_size * self.QUEUE_SIZE_FACTOR
        self._purge()

    def inv(self) -> None:
        global inv_failed

        # the keys of the queue and cache should be identical
        cache_keys = set(self.cache.keys())
        queue_keys = set(self.queue)
        if queue_keys - cache_keys:
            log.msg("INV: uncached keys in queue:", queue_keys - cache_keys)
            inv_failed = True
        if cache_keys - queue_keys:
            log.msg("INV: unqueued keys in cache:", cache_keys - queue_keys)
            inv_failed = True

        # refcount should always represent the number of times each key appears
        # in the queue
        exp_refcount: dict[_KT, int] = {}
        for k in self.queue:
            exp_refcount[k] = exp_refcount.get(k, 0) + 1
        if exp_refcount != self.refcount:
            log.msg("INV: refcounts differ:")
            log.msg(" expected:", sorted(exp_refcount.items()))
            log.msg("      got:", sorted(self.refcount.items()))
            inv_failed = True

    def _ref_key(self, key: _KT) -> None:
        """Record a reference to the argument key."""
        queue = self.queue
        refcount = self.refcount

        queue.append(key)
        refcount[key] = refcount[key] + 1

        # periodically compact the queue by eliminating duplicate keys
        # while preserving order of most recent access.  Note that this
        # is only required when the cache does not exceed its maximum
        # size
        if len(queue) > self.max_queue:
            refcount.clear()
            queue_appendleft = queue.appendleft
            queue_appendleft(self.sentinel)  # type: ignore[arg-type]
            for k in filterfalse(refcount.__contains__, iter(queue.pop, self.sentinel)):
                queue_appendleft(k)
                refcount[k] = 1

    def _get_hit(self, key: _KT) -> _KV:
        """Try to do a value lookup from the existing cache entries."""
        try:
            result = self.cache[key]
            self.hits += 1
            self._ref_key(key)
            return result
        except KeyError:
            pass

        result = self.weakrefs[key]
        self.refhits += 1
        self.cache[key] = result
        self._ref_key(key)
        return result

    def _purge(self) -> None:
        """
        Trim the cache down to max_size by evicting the
        least-recently-used entries.
        """
        if len(self.cache) <= self.max_size:
            return

        cache = self.cache
        refcount = self.refcount
        queue = self.queue
        max_size = self.max_size

        # purge least recently used entries, using refcount to count entries
        # that appear multiple times in the queue
        while len(cache) > max_size:
            refc = 1
            while refc:
                k = queue.popleft()
                refc = refcount[k] = refcount[k] - 1
            del cache[k]
            del refcount[k]


class AsyncLRUCache(LRUCache[_KT, _KV]):
    """
    An LRU cache with asynchronous locking to ensure that in the common case of
    multiple concurrent requests for the same key, only one fetch is performed.
    """

    __slots__ = ['concurrent']

    def __init__(
        self, miss_fn: Callable[Concatenate[_KT, ...], Deferred[_KV]], max_size: int = 50
    ) -> None:
        super().__init__(
            miss_fn,  # type: ignore[arg-type]
            max_size=max_size,
        )
        self.concurrent: dict[_KT, list[Deferred[_KV]]] = {}

        self.miss_fn: Callable[Concatenate[_KT, ...], Deferred[_KV]] = miss_fn  # type: ignore[assignment]

    def get(  # type: ignore[override]
        self,
        key: _KT,
        **miss_fn_kwargs: Any,
    ) -> Deferred[_KV]:
        try:
            result = self._get_hit(key)
            return defer.succeed(result)
        except KeyError:
            pass

        concurrent = self.concurrent
        conc = concurrent.get(key)
        if conc:
            self.hits += 1
            d: Deferred[_KV] = defer.Deferred()
            conc.append(d)
            return d

        # if we're here, we've missed and need to fetch
        self.misses += 1

        # create a list of waiting deferreds for this key
        d = defer.Deferred()
        assert key not in concurrent
        concurrent[key] = [d]

        miss_d = self.miss_fn(key, **miss_fn_kwargs)

        def handle_result(result: _KV) -> None:
            if result is not None:
                self.cache[key] = result
                self.weakrefs[key] = result

                # reference the key once, possibly standing in for multiple
                # concurrent accesses
                self._ref_key(key)

                self._purge()

            # and fire all of the waiting Deferreds
            dlist = concurrent.pop(key)
            for d in dlist:
                d.callback(result)

        def handle_failure(f: Failure) -> None:
            # errback all of the waiting Deferreds
            dlist = concurrent.pop(key)
            for d in dlist:
                d.errback(f)

        miss_d.addCallbacks(handle_result, handle_failure)
        miss_d.addErrback(log.err)

        return d


# for tests
inv_failed = False
