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
from buildbot import cache

class CacheManager(unittest.TestCase):

    def setUp(self):
        self.caches = cache.CacheManager()

    def test_get_cache_idempotency(self):
        foo_cache = self.caches.get_cache("foo", None)
        bar_cache = self.caches.get_cache("bar", None)
        foo_cache2 = self.caches.get_cache("foo", None)
        self.assertIdentical(foo_cache, foo_cache2)
        self.assertNotIdentical(foo_cache, bar_cache)

    def test_load_config(self):
        # load config with one cache loaded and the other not
        foo_cache = self.caches.get_cache("foo", None)
        self.caches.load_config({'foo' : 5, 'bar' : 6, 'bing' : 11})
        bar_cache = self.caches.get_cache("bar", None)
        self.assertEqual((foo_cache.max_size, bar_cache.max_size),
                         (5, 6))
