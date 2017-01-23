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
from future.utils import iteritems

from buildbot.util import lru
from buildbot.util import service


class CacheManager(service.ReconfigurableServiceMixin, service.AsyncService):

    """
    A manager for a collection of caches, each for different types of objects
    and with potentially-overlapping key spaces.

    There is generally only one instance of this class, available at
    C{master.caches}.
    """

    # a cache of length one still has many benefits: it collects objects that
    # remain referenced elsewhere; it collapses simultaneous misses into one
    # miss function; and it will optimize repeated fetches of the same object.
    DEFAULT_CACHE_SIZE = 1

    def __init__(self):
        self.setName('caches')
        self.config = {}
        self._caches = {}

    def get_cache(self, cache_name, miss_fn):
        """
        Get an L{AsyncLRUCache} object with the given name.  If such an object
        does not exist, it will be created.  Since the cache is permanent, this
        method can be called only once, e.g., in C{startService}, and it value
        stored indefinitely.

        @param cache_name: name of the cache (usually the name of the type of
        object it stores)
        @param miss_fn: miss function for the cache; see L{AsyncLRUCache}
        constructor.
        @returns: L{AsyncLRUCache} instance
        """
        try:
            return self._caches[cache_name]
        except KeyError:
            max_size = self.config.get(cache_name, self.DEFAULT_CACHE_SIZE)
            assert max_size >= 1
            c = self._caches[cache_name] = lru.AsyncLRUCache(miss_fn, max_size)
            return c

    def reconfigServiceWithBuildbotConfig(self, new_config):
        self.config = new_config.caches
        for name, cache in iteritems(self._caches):
            cache.set_max_size(new_config.caches.get(name,
                                                     self.DEFAULT_CACHE_SIZE))

        return service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(self,
                                                                                    new_config)

    def get_metrics(self):
        return dict([
            (n, dict(hits=c.hits, refhits=c.refhits,
                     misses=c.misses, max_size=c.max_size))
            for n, c in iteritems(self._caches)])
