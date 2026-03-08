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
from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process import cache

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class CacheManager(unittest.TestCase):
    def setUp(self) -> None:
        self.caches = cache.CacheManager()

    def make_config(self, **kwargs: int) -> mock.Mock:
        cfg = mock.Mock()
        cfg.caches = kwargs
        return cfg

    def test_get_cache_idempotency(self) -> None:
        foo_cache = self.caches.get_cache("foo", None)  # type: ignore[arg-type]
        bar_cache = self.caches.get_cache("bar", None)  # type: ignore[arg-type]
        foo_cache2 = self.caches.get_cache("foo", None)  # type: ignore[arg-type]
        self.assertIdentical(foo_cache, foo_cache2)
        self.assertNotIdentical(foo_cache, bar_cache)

    @defer.inlineCallbacks
    def test_reconfigServiceWithBuildbotConfig(self) -> InlineCallbacksType[None]:
        # load config with one cache loaded and the other not
        foo_cache = self.caches.get_cache("foo", None)  # type: ignore[arg-type]
        yield self.caches.reconfigServiceWithBuildbotConfig(self.make_config(foo=5, bar=6, bing=11))

        bar_cache = self.caches.get_cache("bar", None)  # type: ignore[arg-type]
        self.assertEqual((foo_cache.max_size, bar_cache.max_size), (5, 6))

    def test_get_metrics(self) -> None:
        self.caches.get_cache("foo", None)  # type: ignore[arg-type]
        self.assertIn('foo', self.caches.get_metrics())
        metric = self.caches.get_metrics()['foo']
        for k in 'hits', 'refhits', 'misses', 'max_size':
            self.assertIn(k, metric)
