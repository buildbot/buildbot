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

import json

import sqlalchemy as sa
import sqlalchemy.exc

from buildbot.db import base


class _IdNotFoundError(Exception):
    pass  # used internally


class ObjDict(dict):
    pass


class StateConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/db.rst

    def getObjectId(self, name, class_name):
        # defer to a cached method that only takes one parameter (a tuple)
        d = self._getObjectId((name, class_name))
        d.addCallback(lambda objdict: objdict['id'])
        return d

    @base.cached('objectids')
    def _getObjectId(self, name_class_name_tuple):
        name, class_name = name_class_name_tuple

        def thd(conn):
            return self.thdGetObjectId(conn, name, class_name)
        return self.db.pool.do(thd)

    def thdGetObjectId(self, conn, name, class_name):
        objects_tbl = self.db.model.objects

        self.checkLength(objects_tbl.c.name, name)
        self.checkLength(objects_tbl.c.class_name, class_name)

        def select():
            q = sa.select([objects_tbl.c.id],
                          whereclause=((objects_tbl.c.name == name)
                                       & (objects_tbl.c.class_name == class_name)))
            res = conn.execute(q)
            row = res.fetchone()
            res.close()
            if not row:
                raise _IdNotFoundError
            return row.id

        def insert():
            res = conn.execute(objects_tbl.insert(),
                               name=name,
                               class_name=class_name)
            return res.inserted_primary_key[0]

        # we want to try selecting, then inserting, but if the insert fails
        # then try selecting again.  We include an invocation of a hook
        # method to allow tests to exercise this particular behavior
        try:
            return ObjDict(id=select())
        except _IdNotFoundError:
            pass

        self._test_timing_hook(conn)

        try:
            return ObjDict(id=insert())
        except (sqlalchemy.exc.IntegrityError,
                sqlalchemy.exc.ProgrammingError):
            pass

        return ObjDict(id=select())

    class Thunk:
        pass

    def getState(self, objectid, name, default=Thunk):
        def thd(conn):
            return self.thdGetState(conn, objectid, name, default=default)
        return self.db.pool.do(thd)

    def thdGetState(self, conn, objectid, name, default=Thunk):
        object_state_tbl = self.db.model.object_state

        q = sa.select([object_state_tbl.c.value_json],
                      whereclause=((object_state_tbl.c.objectid == objectid)
                                   & (object_state_tbl.c.name == name)))
        res = conn.execute(q)
        row = res.fetchone()
        res.close()

        if not row:
            if default is self.Thunk:
                raise KeyError("no such state value '%s' for object %d" %
                               (name, objectid))
            return default
        try:
            return json.loads(row.value_json)
        except ValueError:
            raise TypeError("JSON error loading state value '%s' for %d" %
                            (name, objectid))

    def setState(self, objectid, name, value):
        def thd(conn):
            return self.thdSetState(conn, objectid, name, value)
        return self.db.pool.do(thd)

    def thdSetState(self, conn, objectid, name, value):
        object_state_tbl = self.db.model.object_state

        try:
            value_json = json.dumps(value)
        except (TypeError, ValueError):
            raise TypeError("Error encoding JSON for %r" % (value,))

        self.checkLength(object_state_tbl.c.name, name)

        def update():
            q = object_state_tbl.update(
                whereclause=((object_state_tbl.c.objectid == objectid)
                             & (object_state_tbl.c.name == name)))
            res = conn.execute(q, value_json=value_json)

            # check whether that worked
            return res.rowcount > 0

        def insert():
            conn.execute(object_state_tbl.insert(),
                         objectid=objectid,
                         name=name,
                         value_json=value_json)

        # try updating; if that fails, try inserting; if that fails, then
        # we raced with another instance to insert, so let that instance
        # win.

        if update():
            return

        self._test_timing_hook(conn)

        try:
            insert()
        except (sqlalchemy.exc.IntegrityError, sqlalchemy.exc.ProgrammingError):
            pass  # someone beat us to it - oh well

    def _test_timing_hook(self, conn):
        # called so tests can simulate another process inserting a database row
        # at an inopportune moment
        pass

    def atomicCreateState(self, objectid, name, thd_create_callback):
        def thd(conn):
            object_state_tbl = self.db.model.object_state
            res = self.thdGetState(conn, objectid, name, default=None)
            if res is None:
                res = thd_create_callback()
                try:
                    value_json = json.dumps(res)
                except (TypeError, ValueError):
                    raise TypeError("Error encoding JSON for %r" % (res,))
                self._test_timing_hook(conn)
                try:
                    conn.execute(object_state_tbl.insert(),
                                 objectid=objectid,
                                 name=name,
                                 value_json=value_json)
                except (sqlalchemy.exc.IntegrityError, sqlalchemy.exc.ProgrammingError):
                    # someone beat us to it - oh well return that value
                    return self.thdGetState(conn, objectid, name)
            return res
        return self.db.pool.do(thd)
