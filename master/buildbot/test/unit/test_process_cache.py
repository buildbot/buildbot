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

from __future__ import absolute_import
from __future__ import print_function

import mock

from twisted.trial import unittest

from buildbot.process import cache


class CacheManager(unittest.TestCase):

    def setUp(self):
        self.caches = cache.CacheManager()

    def make_config(self, **kwargs):
        cfg = mock.Mock()
        cfg.caches = kwargs
        return cfg

    def test_get_cache_idempotency(self):
        foo_cache = self.caches.get_cache("foo", None)
        bar_cache = self.caches.get_cache("bar", None)
        foo_cache2 = self.caches.get_cache("foo", None)
        self.assertIdentical(foo_cache, foo_cache2)
        self.assertNotIdentical(foo_cache, bar_cache)

    def test_reconfigServiceWithBuildbotConfig(self):
        # load config with one cache loaded and the other not
        foo_cache = self.caches.get_cache("foo", None)
        d = self.caches.reconfigServiceWithBuildbotConfig(
            self.make_config(foo=5, bar=6, bing=11))

        @d.addCallback
        def check(_):
            bar_cache = self.caches.get_cache("bar", None)
            self.assertEqual((foo_cache.max_size, bar_cache.max_size),
                             (5, 6))

    def test_get_metrics(self):
        self.caches.get_cache("foo", None)
        self.assertIn('foo', self.caches.get_metrics())
        metric = self.caches.get_metrics()['foo']
        for k in 'hits', 'refhits', 'misses', 'max_size':
            self.assertIn(k, metric)
