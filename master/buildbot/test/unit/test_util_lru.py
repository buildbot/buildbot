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

import string
import random
from twisted.trial import unittest
from twisted.internet import defer, reactor
from buildbot.util import lru

# construct weakref-able objects for particular keys
def short(k):
    return set([k.upper() * 3])
def long(k):
    return set([k.upper() * 6])

class LRUCache(unittest.TestCase):

    def setUp(self):
        self.lru = lru.AsyncLRUCache(3)

    def short_miss_fn(self, key):
        return defer.succeed(short(key))

    def long_miss_fn(self, key):
        return defer.succeed(long(key))

    def failure_miss_fn(self, key):
        return defer.succeed(None)

    def check_result(self, r, exp, exp_hits=None, exp_misses=None,
                            exp_refhits=None):
        self.assertEqual(r, exp)
        if exp_hits is not None:
            self.assertEqual(self.lru.hits, exp_hits)
        if exp_misses is not None:
            self.assertEqual(self.lru.misses, exp_misses)
        if exp_refhits is not None:
            self.assertEqual(self.lru.refhits, exp_refhits)

    # tests

    def test_single_key(self):
        # just get an item
        d = self.lru.get('a', self.short_miss_fn)
        d.addCallback(self.check_result, short('a'), 0, 1)

        # second time, it should be cached..
        d.addCallback(lambda _ :
            self.lru.get('a', self.long_miss_fn))
        d.addCallback(self.check_result, short('a'), 1, 1)
        return d

    def test_simple_lru_expulsion(self):
        d = defer.succeed(None)

        d.addCallback(lambda _ :
            self.lru.get('a', self.short_miss_fn))
        d.addCallback(self.check_result, short('a'), 0, 1)
        d.addCallback(lambda _ :
            self.lru.get('b', self.short_miss_fn))
        d.addCallback(self.check_result, short('b'), 0, 2)
        d.addCallback(lambda _ :
            self.lru.get('c', self.short_miss_fn))
        d.addCallback(self.check_result, short('c'), 0, 3)
        d.addCallback(lambda _ :
            self.lru.get('d', self.short_miss_fn))
        d.addCallback(self.check_result, short('d'), 0, 4)

        # now try 'a' again - it should be a miss
        d.addCallback(lambda _ :
            self.lru.get('a', self.long_miss_fn))
        d.addCallback(self.check_result, long('a'), 0, 5)

        # ..and that expelled B, but C is still in the cache
        d.addCallback(lambda _ :
            self.lru.get('c', self.long_miss_fn))
        d.addCallback(self.check_result, short('c'), 1, 5)
        return d

    @defer.deferredGenerator
    def test_queue_collapsing(self):
        # just to check that we're practicing with the right queue size
        self.assertEqual(self.lru.max_queue, 30)

        for c in 'a' + 'x' * 27 + 'ab':
            wfd = defer.waitForDeferred(
                    self.lru.get(c, self.short_miss_fn))
            yield wfd
            res = wfd.getResult()
        self.check_result(res, short('b'), 27, 3)

        # at this point, we should have 'x', 'a', and 'b' in the cache,
        # and a, lots of x's, and ab in the queue.  The next get operation
        # should evict 'x', not 'a'.

        wfd = defer.waitForDeferred(
                self.lru.get('c', self.short_miss_fn))
        yield wfd
        res = wfd.getResult()
        self.check_result(res, short('c'), 27, 4)

        # expect a cached short('a')
        wfd = defer.waitForDeferred(
                self.lru.get('a', self.long_miss_fn))
        yield wfd
        res = wfd.getResult()
        self.check_result(res, short('a'), 28, 4)

        # expect a newly minted long('x')
        wfd = defer.waitForDeferred(
                self.lru.get('x', self.long_miss_fn))
        yield wfd
        res = wfd.getResult()
        self.check_result(res, long('x'), 28, 5)

    @defer.deferredGenerator
    def test_all_misses(self):
        for i, c in enumerate(string.lowercase + string.uppercase):
            wfd = defer.waitForDeferred(
                    self.lru.get(c, self.short_miss_fn))
            yield wfd
            res = wfd.getResult()
            self.check_result(res, short(c), 0, i+1)

    @defer.deferredGenerator
    def test_all_hits(self):
        wfd = defer.waitForDeferred(
                self.lru.get('a', self.short_miss_fn))
        yield wfd
        res = wfd.getResult()
        self.check_result(res, short('a'), 0, 1)

        for i in xrange(100):
            wfd = defer.waitForDeferred(
                    self.lru.get('a', self.long_miss_fn))
            yield wfd
            res = wfd.getResult()
            self.check_result(res, short('a'), i+1, 1)

    @defer.deferredGenerator
    def test_weakrefs(self):
        wfd = defer.waitForDeferred(
                self.lru.get('a', self.short_miss_fn))
        yield wfd
        res_a = wfd.getResult()
        self.check_result(res_a, short('a'))
        # note that res_a keeps a reference to this value

        wfd = defer.waitForDeferred(
                self.lru.get('b', self.short_miss_fn))
        yield wfd
        res_b = wfd.getResult()
        self.check_result(res_b, short('b'))
        del res_b # discard reference to b

        # blow out the cache and the queue
        for c in (string.lowercase[2:] * 5):
            wfd = defer.waitForDeferred(
                    self.lru.get(c, self.long_miss_fn))
            yield wfd
            wfd.getResult()

        # and fetch a again, expecting the cached value
        wfd = defer.waitForDeferred(
                self.lru.get('a', self.long_miss_fn))
        yield wfd
        res = wfd.getResult()
        self.check_result(res, short('a'), exp_refhits=1)

        # but 'b' should give us a new value
        wfd = defer.waitForDeferred(
                self.lru.get('b', self.long_miss_fn))
        yield wfd
        res = wfd.getResult()
        self.check_result(res, long('b'), exp_refhits=1)

    @defer.deferredGenerator
    def test_fuzz(self):
        chars = list(string.lowercase * 40)
        random.shuffle(chars)
        for i, c in enumerate(chars):
            wfd = defer.waitForDeferred(
                    self.lru.get(c, self.short_miss_fn))
            yield wfd
            res = wfd.getResult()
            self.check_result(res, short(c))

    def test_massively_parallel(self):
        chars = list(string.lowercase * 5)

        misses = [ 0 ]
        def slow_short_miss_fn(key):
            d = defer.Deferred()
            misses[0] += 1
            reactor.callLater(0, lambda : d.callback(short(key)))
            return d

        def check(c, d):
            d.addCallback(self.check_result, short(c))
            return d
        d = defer.gatherResults([
            check(c, self.lru.get(c, slow_short_miss_fn))
            for c in chars ])
        def post_check(_):
            self.assertEqual(misses[0], 26)
            self.assertEqual(self.lru.misses, 26)
            self.assertEqual(self.lru.hits, 4*26)
        d.addCallback(post_check)
        return d

    def test_slow_fetch(self):
        def slower_miss_fn(k):
            d = defer.Deferred()
            reactor.callLater(0.05, lambda : d.callback(short(k)))
            return d

        def do_get(test_d, k):
            d = self.lru.get(k, slower_miss_fn)
            d.addCallback(self.check_result, short(k))
            d.addCallbacks(test_d.callback, test_d.errback)

        ds = []
        for i in range(8):
            d = defer.Deferred()
            reactor.callLater(0.02*i, do_get, d, 'x')
            ds.append(d)

        d = defer.gatherResults(ds)
        def check(_):
            self.assertEqual((self.lru.hits, self.lru.misses), (7, 1))
        d.addCallback(check)
        return d
