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

from buildbot.util import json
import sqlalchemy as sa
import sqlalchemy.exc
from buildbot.db import base

class _IdNotFoundError(Exception):
    pass # used internally

class StateConnectorComponent(base.DBConnectorComponent):
    """
    A DBConnectorComponent to handle maintaining arbitrary key/value state for
    Buildbot objects.  Objects are identified by their (user-visible) name and
    their class.  This allows e.g., a 'nightly_smoketest' object of class
    NightlyScheduler to maintain its state even if it moves between masters,
    but avoids cross-contaminating state between different classes.

    Note that the class is not interpreted literally, and can be any string
    that will uniquely identify the class for the object; if classes are
    renamed, they can continue to use the old names.
    """

    def getObjectId(self, name, class_name):
        """
        Get the object ID for this combination of a name and a class.  This
        will add a row to the 'objects' table if none exists already.

        @param name: name of the object
        @param class_name: object class name
        @returns: the objectid, via a Deferred.
        """
        def thd(conn):
            objects_tbl = self.db.model.objects

            def select():
                q = sa.select([ objects_tbl.c.id ],
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
                return select()
            except _IdNotFoundError:
                pass

            self._test_timing_hook(conn)

            try:
                return insert()
            except (sqlalchemy.exc.IntegrityError, sqlalchemy.exc.ProgrammingError):
                pass

            return select()

        return self.db.pool.do(thd)

    class Thunk: pass
    def getState(self, objectid, name, default=Thunk):
        """
        Get the state value for C{name} for the object with id C{objectid}.

        @param objectid: objectid on which the state should be checked
        @param name: name of the value to retrieve
        @param default: (optional) value to return if C{name} is not present
        @returns: state value via a Deferred
        @raises KeyError: if C{name} is not present and no default is given
        @raises TypeError: if JSON parsing fails
        """

        def thd(conn):
            object_state_tbl = self.db.model.object_state
            q = sa.select([ object_state_tbl.c.value_json ],
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
            except:
                raise TypeError("JSON error loading state value '%s' for %d" %
                                (name, objectid))
        return self.db.pool.do(thd)

    def setState(self, objectid, name, value):
        """
        Set the state value for C{name} for the object with id C{objectid},
        overwriting any existing value.

        @param objectid: the objectid for which the state should be changed
        @param name: the name of the value to change
        @param value: the value to set - must be a JSONable object
        @param returns: Deferred
        @raises TypeError: if JSONification fails
        """
        def thd(conn):
            object_state_tbl = self.db.model.object_state

            try:
                value_json = json.dumps(value)
            except:
                raise TypeError("Error encoding JSON for %r" % (value,))

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
                pass # someone beat us to it - oh well

        return self.db.pool.do(thd)

    def _test_timing_hook(self, conn):
        # called so tests can simulate another process inserting a database row
        # at an inopportune moment
        pass

