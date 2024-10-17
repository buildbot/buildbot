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

import dataclasses
from typing import TYPE_CHECKING

import sqlalchemy as sa
from twisted.python import deprecate
from twisted.python import versions

from buildbot.db import base
from buildbot.util import identifiers
from buildbot.warnings import warn_deprecated

if TYPE_CHECKING:
    from twisted.internet import defer


@dataclasses.dataclass
class UserModel:
    uid: int
    identifier: str
    bb_username: str | None = None
    bb_password: str | None = None
    attributes: dict[str, str] | None = None

    # For backward compatibility
    def __getitem__(self, key: str):
        warn_deprecated(
            '4.1.0',
            (
                'UsersConnectorComponent '
                'getUser, getUserByUsername, and getUsers '
                'no longer return User as dictionnaries. '
                'Usage of [] accessor is deprecated: please access the member directly'
            ),
        )

        if hasattr(self, key):
            return getattr(self, key)

        if self.attributes is not None and key in self.attributes:
            return self.attributes[key]

        raise KeyError(key)


@deprecate.deprecated(versions.Version("buildbot", 4, 1, 0), UserModel)
class UsDict(UserModel):
    pass


class UsersConnectorComponent(base.DBConnectorComponent):
    def findUserByAttr(
        self, identifier: str, attr_type: str, attr_data: str, _race_hook=None
    ) -> defer.Deferred[int]:
        # note that since this involves two tables, self.findSomethingId is not
        # helpful
        def thd(conn, no_recurse=False, identifier=identifier) -> int:
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info

            self.checkLength(tbl.c.identifier, identifier)
            self.checkLength(tbl_info.c.attr_type, attr_type)
            self.checkLength(tbl_info.c.attr_data, attr_data)

            # try to find the user
            q = sa.select(
                tbl_info.c.uid,
            ).where(tbl_info.c.attr_type == attr_type, tbl_info.c.attr_data == attr_data)
            rows = conn.execute(q).fetchall()

            if rows:
                return rows[0].uid

            if _race_hook is not None:
                _race_hook(conn)

            # try to do both of these inserts in a transaction, so that both
            # the new user and the corresponding attributes appear at the same
            # time from the perspective of other masters.
            transaction = conn.begin_nested()
            inserted_user = False
            try:
                r = conn.execute(tbl.insert(), {"identifier": identifier})
                uid = r.inserted_primary_key[0]
                inserted_user = True

                conn.execute(
                    tbl_info.insert(), {"uid": uid, "attr_type": attr_type, "attr_data": attr_data}
                )

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
                    identifier = identifiers.incrementIdentifier(256, identifier)
                else:
                    no_recurse = True

                return thd(conn, no_recurse=no_recurse, identifier=identifier)

            conn.commit()
            return uid

        return self.db.pool.do(thd)

    @base.cached("usdicts")
    def getUser(self, uid: int) -> defer.Deferred[UserModel | None]:
        def thd(conn) -> UserModel | None:
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info

            q = tbl.select().where(tbl.c.uid == uid)
            users_row = conn.execute(q).fetchone()

            if not users_row:
                return None

            # gather all attr_type and attr_data entries from users_info table
            q = tbl_info.select().where(tbl_info.c.uid == uid)
            rows = conn.execute(q).fetchall()

            return self._model_from_row(users_row, rows)

        return self.db.pool.do(thd)

    def _model_from_row(self, users_row, attribute_rows=None):
        attributes = None
        if attribute_rows is not None:
            attributes = {row.attr_type: row.attr_data for row in attribute_rows}
        return UserModel(
            uid=users_row.uid,
            identifier=users_row.identifier,
            bb_username=users_row.bb_username,
            bb_password=users_row.bb_password,
            attributes=attributes,
        )

    # returns a Deferred that returns a value
    def getUserByUsername(self, username: str | None) -> defer.Deferred[UserModel | None]:
        def thd(conn) -> UserModel | None:
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info

            q = tbl.select().where(tbl.c.bb_username == username)
            users_row = conn.execute(q).fetchone()

            if not users_row:
                return None

            # gather all attr_type and attr_data entries from users_info table
            q = tbl_info.select().where(tbl_info.c.uid == users_row.uid)
            rows = conn.execute(q).fetchall()

            return self._model_from_row(users_row, rows)

        return self.db.pool.do(thd)

    def getUsers(self) -> defer.Deferred[list[UserModel]]:
        def thd(conn) -> list[UserModel]:
            tbl = self.db.model.users
            rows = conn.execute(tbl.select()).fetchall()

            return [self._model_from_row(row, attribute_rows=None) for row in rows]

        return self.db.pool.do(thd)

    # returns a Deferred that returns None
    def updateUser(
        self,
        uid: int | None = None,
        identifier: str | None = None,
        bb_username: str | None = None,
        bb_password: str | None = None,
        attr_type: str | None = None,
        attr_data: str | None = None,
        _race_hook=None,
    ):
        def thd(conn):
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
                q = tbl.update().where(tbl.c.uid == uid)
                conn.execute(q, update_dict)

            # then, update the attributes, carefully handling the potential
            # update-or-insert race condition.
            if attr_type is not None:
                assert attr_data is not None

                self.checkLength(tbl_info.c.attr_type, attr_type)
                self.checkLength(tbl_info.c.attr_data, attr_data)

                try:
                    self.db.upsert(
                        conn,
                        tbl_info,
                        where_values=(
                            (tbl_info.c.uid, uid),
                            (tbl_info.c.attr_type, attr_type),
                        ),
                        update_values=((tbl_info.c.attr_data, attr_data),),
                        _race_hook=_race_hook,
                    )
                    conn.commit()
                except (sa.exc.IntegrityError, sa.exc.ProgrammingError):
                    # someone else beat us to the punch inserting this row;
                    # let them win.
                    conn.rollback()

        return self.db.pool.do_with_transaction(thd)

    # returns a Deferred that returns None
    def removeUser(self, uid):
        def thd(conn):
            # delete from dependent tables first, followed by 'users'
            for tbl in [
                self.db.model.change_users,
                self.db.model.users_info,
                self.db.model.users,
            ]:
                conn.execute(tbl.delete().where(tbl.c.uid == uid))

        return self.db.pool.do_with_transaction(thd)

    # returns a Deferred that returns a value
    def identifierToUid(self, identifier) -> defer.Deferred[int | None]:
        def thd(conn) -> int | None:
            tbl = self.db.model.users

            q = tbl.select().where(tbl.c.identifier == identifier)
            row = conn.execute(q).fetchone()
            if not row:
                return None

            return row.uid

        return self.db.pool.do(thd)
