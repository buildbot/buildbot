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
from future.utils import text_type

import hashlib
import itertools

import sqlalchemy as sa


class DBConnectorComponent(object):
    # A fixed component of the DBConnector, handling one particular aspect of
    # the database.  Instances of subclasses are assigned to attributes of the
    # DBConnector object, so that they are available at e.g.,
    # C{master.db.model} or C{master.db.changes}.  This parent class takes care
    # of the necessary backlinks and other housekeeping.

    connector = None
    data2db = {}

    def __init__(self, connector):
        self.db = connector

        # set up caches
        for method in dir(self.__class__):
            o = getattr(self, method)
            if isinstance(o, CachedMethod):
                setattr(self, method, o.get_cached_method(self))

    @property
    def master(self):
        return self.db.master

    _isCheckLengthNecessary = None

    def checkLength(self, col, value):

        if not self._isCheckLengthNecessary:
            if self.db.pool.engine.dialect.name == 'mysql':
                self._isCheckLengthNecessary = True
            else:
                # not necessary, so just stub out the method
                self.checkLength = lambda col, value: None
                return

        assert col.type.length, "column %s does not have a length" % (col,)
        if value and len(value) > col.type.length:
            raise RuntimeError(
                "value for column %s is greater than max of %d characters: %s"
                % (col, col.type.length, value))

    def findSomethingId(self, tbl, whereclause, insert_values,
                        _race_hook=None):
        def thd(conn, no_recurse=False):
            # try to find the master
            q = sa.select([tbl.c.id],
                          whereclause=whereclause)
            r = conn.execute(q)
            row = r.fetchone()
            r.close()

            # found it!
            if row:
                return row.id

            _race_hook and _race_hook(conn)

            try:
                r = conn.execute(tbl.insert(), [insert_values])
                return r.inserted_primary_key[0]
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                # try it all over again, in case there was an overlapping,
                # identical call, but only retry once.
                if no_recurse:
                    raise
                return thd(conn, no_recurse=True)
        return self.db.pool.do(thd)

    def hashColumns(self, *args):
        def encode(x):
            if x is None:
                return b'\xf5'
            elif isinstance(x, text_type):
                return x.encode('utf-8')
            return str(x).encode('utf-8')

        return hashlib.sha1(b'\0'.join(map(encode, args))).hexdigest()

    def doBatch(self, batch, batch_n=500):
        iterator = iter(batch)
        while True:
            batch = list(itertools.islice(iterator, batch_n))
            if not batch:
                break
            yield batch


class CachedMethod(object):

    def __init__(self, cache_name, method):
        self.cache_name = cache_name
        self.method = method

    def get_cached_method(self, component):
        meth = self.method

        meth_name = meth.__name__
        cache = component.db.master.caches.get_cache(self.cache_name,
                                                     lambda key: meth(component, key))

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
    return lambda method: CachedMethod(cache_name, method)
