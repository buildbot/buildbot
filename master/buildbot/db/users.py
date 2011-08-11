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
Support for users in the database
"""

import sqlalchemy as sa
from sqlalchemy.sql.expression import and_

from buildbot.db import base

class UsDict(dict):
    pass

class MultipleMatchingUsersError(Exception):
    pass

class UsersConnectorComponent(base.DBConnectorComponent):
    """
    A DBConnectorComponent to handle getting users into and out of the
    database.  An instance is available at C{master.db.users}.

    Users are represented as user dictionaries, with keys C{uid},
    C{identifier}, and all attribute types for the given user.  Attribute types
    with conflicting names will be ignored.
    """

    def addUser(self, identifier, attr_type, attr_data, _race_hook=None):
        """
        Get an existing user, or add a new one, based on the given attribute.

        This method is intended for use by other components of Buildbot, for
        identifying users that may relate to Buildbot in several ways, e.g.,
        IRC and Mercurial.  The IRC plugin would use an C{irc} attribute, while
        Mercurial would use an C{hg} attribute, but both would find the same
        user id.

        Note that C{identifier} is I{not} used in the search for an existing
        user.  The identifier should be based on the attributes, and care
        should be taken to avoid calling this method with the same attribute
        arguments but different identifiers, as this can lead to creation of
        multiple users.

        For future compatibility, always use keyword parameters to call this
        method.

        @param identifier: identifier to use for a new user
        @param attr_type: attribute type to search for and/or add
        @param attr_data: attribute data to add
        @param _race_hook: for testing
        @returns: user id via Deferred
        """
        def thd(conn, no_recurse=False):
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info

            # try to find the user
            q = sa.select([ tbl.c.uid ],
                        whereclause=and_(tbl_info.c.attr_type == attr_type,
                                tbl_info.c.attr_data == attr_data))
            rows = conn.execute(q).fetchall()
            if rows:
                return rows[0].uid

            _race_hook and _race_hook(conn)

            # try to do both of these inserts in a transaction, so that both
            # the new user and the corresponding attributes appear at the same
            # time from the perspective of other masters.
            transaction = conn.begin()
            try:
                r = conn.execute(tbl.insert(), dict(identifier=identifier))
                uid = r.inserted_primary_key[0]

                conn.execute(tbl_info.insert(),
                        dict(uid=uid, attr_type=attr_type,
                             attr_data=attr_data))

                transaction.commit()
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                transaction.rollback()

                # try it all over again, in case there was an overlapping,
                # identical call to addUser, but only retry once.
                if no_recurse:
                    raise
                return thd(conn, no_recurse=True)

            return uid
        d = self.db.pool.do(thd)
        return d

    @base.cached("usdicts")
    def getUser(self, uid):
        """
        Get a dictionary representing a given user, or None if no matching
        user is found.

        @param uid: user id to look up
        @type key: int or string

        @param no_cache: bypass cache and always fetch from database
        @type no_cache: boolean

        @returns: User dictionary via deferred
        """
        def thd(conn):
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info

            q = tbl.select(whereclause=(tbl.c.uid == uid))
            users_row = conn.execute(q).fetchone()

            if not users_row:
                return None

            # make UsDict to return
            usdict = UsDict()

            # gather all attr_type and attr_data entries from users_info table
            q = tbl_info.select(whereclause=(tbl_info.c.uid == uid))
            rows = conn.execute(q).fetchall()
            for row in rows:
                usdict[row.attr_type] = row.attr_data

            # add the users_row data *after* the attributes in case attr_type
            # matches one of these keys.
            usdict['uid'] = users_row.uid
            usdict['identifier'] = users_row.identifier

            return usdict
        d = self.db.pool.do(thd)
        return d

    def updateUser(self, uid=None, identifier=None, attr_type=None,
                   attr_data=None, _race_hook=None):
        """
        Updates the current attribute and identifier for the given user.
        items.  If no user with that uid exists, the method will return
        silently.

        @param uid: user id of the user to change
        @type uid: int

        @param identifier: (optional) new identifier for this user
        @type identifier: string

        @param attr_type: (optional) attribute type to update
        @type attr_type: string

        @param attr_data: (optional) value for C{attr_type}
        @type attr_data: string

        @param _race_hook: for testing

        @returns: Deferred
        """
        def thd(conn):
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info

            # first, update the identifier
            if identifier is not None:
                conn.execute(
                    tbl.update(whereclause=tbl.c.uid == uid),
                    identifier=identifier)

            # then, update the attributes, carefully handling the potential
            # update-or-insert race condition.
            if attr_type is not None:
                assert attr_data is not None

                # first update, then insert
                q = tbl_info.update(
                        whereclause=(tbl_info.c.uid == uid)
                                    & (tbl_info.c.attr_type == attr_type))
                res = conn.execute(q, attr_data=attr_data)
                if res.rowcount > 0:
                    return

                _race_hook and _race_hook(conn)

                # the update hit 0 rows, so try inserting a new one
                try:
                    q = tbl_info.insert()
                    res = conn.execute(q,
                            uid=uid,
                            attr_type=attr_type,
                            attr_data=attr_data)
                except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                    # someone else beat us to the punch inserting this row; let
                    # them win.
                    pass
        d = self.db.pool.do(thd)
        return d

    def removeUser(self, uid):
        """
        Remove the user with the given uid from the database.  This will remove
        the user from any associated tables as well.

        @param uid: unique user id number
        @type uid: int

        @returns: Deferred
        """

        def thd(conn):
            # delete from dependent tables first, followed by 'users'
            for tbl in [
                    self.db.model.change_users,
                    self.db.model.users_info,
                    self.db.model.users,
                    ]:
                conn.execute(tbl.delete(whereclause=(tbl.c.uid==uid)))
        d = self.db.pool.do(thd)
        return d
