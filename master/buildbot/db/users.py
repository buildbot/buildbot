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

import sqlalchemy as sa
from sqlalchemy.sql.expression import and_

from buildbot.db import base
from buildbot.util import identifiers


class UsDict(dict):
    pass


class UsersConnectorComponent(base.DBConnectorComponent):
    # Documentation is in developer/db.rst

    def findUserByAttr(self, identifier, attr_type, attr_data, _race_hook=None):
        # note that since this involves two tables, self.findSomethingId is not
        # helpful
        def thd(conn, no_recurse=False, identifier=identifier):
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info

            self.checkLength(tbl.c.identifier, identifier)
            self.checkLength(tbl_info.c.attr_type, attr_type)
            self.checkLength(tbl_info.c.attr_data, attr_data)

            # try to find the user
            q = sa.select([tbl_info.c.uid],
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
            inserted_user = False
            try:
                r = conn.execute(tbl.insert(), dict(identifier=identifier))
                uid = r.inserted_primary_key[0]
                inserted_user = True

                conn.execute(tbl_info.insert(),
                             dict(uid=uid, attr_type=attr_type,
                                  attr_data=attr_data))

                transaction.commit()
            except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                transaction.rollback()

                # try it all over again, in case there was an overlapping,
                # identical call to findUserByAttr.  If the identifier
                # collided, we'll try again indefinitely; otherwise, only once.
                if no_recurse:
                    raise

                # if we failed to insert the user, then it's because the
                # identifier wasn't unique
                if not inserted_user:
                    identifier = identifiers.incrementIdentifier(
                        256, identifier)
                else:
                    no_recurse = True

                return thd(conn, no_recurse=no_recurse, identifier=identifier)

            return uid
        d = self.db.pool.do(thd)
        return d

    @base.cached("usdicts")
    def getUser(self, uid):
        def thd(conn):
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info

            q = tbl.select(whereclause=(tbl.c.uid == uid))
            users_row = conn.execute(q).fetchone()

            if not users_row:
                return None

            # gather all attr_type and attr_data entries from users_info table
            q = tbl_info.select(whereclause=(tbl_info.c.uid == uid))
            rows = conn.execute(q).fetchall()

            return self.thd_createUsDict(users_row, rows)
        d = self.db.pool.do(thd)
        return d

    def thd_createUsDict(self, users_row, rows):
        # make UsDict to return
        usdict = UsDict()
        for row in rows:
            usdict[row.attr_type] = row.attr_data

        # add the users_row data *after* the attributes in case attr_type
        # matches one of these keys.
        usdict['uid'] = users_row.uid
        usdict['identifier'] = users_row.identifier
        usdict['bb_username'] = users_row.bb_username
        usdict['bb_password'] = users_row.bb_password

        return usdict

    def getUserByUsername(self, username):
        def thd(conn):
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info

            q = tbl.select(whereclause=(tbl.c.bb_username == username))
            users_row = conn.execute(q).fetchone()

            if not users_row:
                return None

            # gather all attr_type and attr_data entries from users_info table
            q = tbl_info.select(whereclause=(tbl_info.c.uid == users_row.uid))
            rows = conn.execute(q).fetchall()

            return self.thd_createUsDict(users_row, rows)
        d = self.db.pool.do(thd)
        return d

    def getUsers(self):
        def thd(conn):
            tbl = self.db.model.users
            rows = conn.execute(tbl.select()).fetchall()

            dicts = []
            if rows:
                for row in rows:
                    ud = dict(uid=row.uid, identifier=row.identifier)
                    dicts.append(ud)
            return dicts
        d = self.db.pool.do(thd)
        return d

    def updateUser(self, uid=None, identifier=None, bb_username=None,
                   bb_password=None, attr_type=None, attr_data=None,
                   _race_hook=None):
        def thd(conn):
            transaction = conn.begin()
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info
            update_dict = {}

            # first, add the identifier is it exists
            if identifier is not None:
                self.checkLength(tbl.c.identifier, identifier)
                update_dict['identifier'] = identifier

            # then, add the creds if they exist
            if bb_username is not None:
                assert bb_password is not None
                self.checkLength(tbl.c.bb_username, bb_username)
                self.checkLength(tbl.c.bb_password, bb_password)
                update_dict['bb_username'] = bb_username
                update_dict['bb_password'] = bb_password

            # update the users table if it needs to be updated
            if update_dict:
                q = tbl.update(whereclause=(tbl.c.uid == uid))
                res = conn.execute(q, update_dict)

            # then, update the attributes, carefully handling the potential
            # update-or-insert race condition.
            if attr_type is not None:
                assert attr_data is not None

                self.checkLength(tbl_info.c.attr_type, attr_type)
                self.checkLength(tbl_info.c.attr_data, attr_data)

                # first update, then insert
                q = tbl_info.update(
                    whereclause=(tbl_info.c.uid == uid)
                    & (tbl_info.c.attr_type == attr_type))
                res = conn.execute(q, attr_data=attr_data)
                if res.rowcount == 0:
                    if _race_hook is not None:
                        _race_hook(conn)

                    # the update hit 0 rows, so try inserting a new one
                    try:
                        q = tbl_info.insert()
                        res = conn.execute(q,
                                           uid=uid,
                                           attr_type=attr_type,
                                           attr_data=attr_data)
                    except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                        # someone else beat us to the punch inserting this row;
                        # let them win.
                        transaction.rollback()
                        return

            transaction.commit()
        d = self.db.pool.do(thd)
        return d

    def removeUser(self, uid):
        def thd(conn):
            # delete from dependent tables first, followed by 'users'
            for tbl in [
                    self.db.model.change_users,
                    self.db.model.users_info,
                    self.db.model.users,
            ]:
                conn.execute(tbl.delete(whereclause=(tbl.c.uid == uid)))
        d = self.db.pool.do(thd)
        return d

    def identifierToUid(self, identifier):
        def thd(conn):
            tbl = self.db.model.users

            q = tbl.select(whereclause=(tbl.c.identifier == identifier))
            row = conn.execute(q).fetchone()
            if not row:
                return None

            return row.uid
        d = self.db.pool.do(thd)
        return d
