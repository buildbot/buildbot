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

"""
Base classes for database handling
"""

class DBConnectorComponent(object):
    """
    A fixed component of the DBConnector, handling one particular aspect of the
    database.  Instances of subclasses are assigned to attributes of the
    DBConnector object, so that they are available at e.g., C{master.db.model}
    or C{master.db.changes}.  This parent class takes care of the necessary
    backlinks and other housekeeping.
    """

    connector = None

    def __init__(self, connector):
        self.db = connector
        "backlink to the DBConnector object"

        # set up caches
        for method in dir(self.__class__):
            o = getattr(self, method)
            if isinstance(o, CachedMethod):
                setattr(self, method, o.get_cached_method(self))

class CachedMethod(object):
    def __init__(self, cache_name, method):
        self.cache_name = cache_name
        self.method = method

    def get_cached_method(self, component):
        meth = self.method

        meth_name = meth.__name__
        cache = component.db.master.caches.get_cache(self.cache_name,
                lambda key : meth(component, key))
        def wrap(key, no_cache=0):
            if no_cache:
                return meth(component, key)
            return cache.get(key)
        wrap.__name__ = meth_name + " (wrapped)"
        wrap.__module__ = meth.__module__
        wrap.__doc__ = meth.__doc__
        wrap.cache = cache
        return wrap

def cached(cache_name):
    """
    A decorator for "getter" functions that fetch an object from the database
    based on a single key.  The wrapped method will only be called if the named
    cache does not contain the key.

    The wrapped function must take one argument (the key); the wrapper will
    take a key plus an optional C{no_cache} argument which, if true, will cause
    it to invoke the underlying method even if the key is in the cache.

    The resulting method will have a C{cache} attribute which can be used to
    access the underlying cache.

    @param cache_name: name of the cache to use
    """
    return lambda method : CachedMethod(cache_name, method)
