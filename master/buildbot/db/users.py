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
from sqlalchemy.sql.expression import and_, or_

from twisted.python import log
from twisted.internet import defer, reactor
from buildbot.db import base

class UsDict(dict):
    pass

class UsersConnectorComponent(base.DBConnectorComponent):
    """
    A DBConnectorComponent to handle getting users into and out of the
    database.  An instance is available at C{master.db.users}.

    """

    known_types = ['full_name', 'email']
    known_info_types = ['authz_user', 'authz_pass', 'git']

    def addUser(self, identifier=None, user_dict=None):
        """Adds a User to the database with the passed in attributes; returns
        the new user's uid via deferred. All arguments are keyword arguments.
        This performs some checks to make sure there aren't duplicate users
        created, such as checking for exact matches on attr_data.

        @param identifier: string used as index if uid is not known
        @type identifier: string

        @param user_dict: dictionary whose key/value pairs are attr_type
                          and attr_data pairs
        @type user_dict: dictionary

        @returns: new user's uid via Deferred or None
        """

        def thd(conn):
            if not user_dict:
                return None

            transaction = conn.begin()
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info
            uid, ident = None, None

            # if there's a user with the same identifier already in the
            # database, we use the existing uid
            if identifier:
                res = conn.execute(tbl.select(whereclause=(
                                      tbl.c.identifier == identifier)))
                rows = res.fetchall()
                if rows:
                    uid = rows[0].uid
                ident = identifier

            # if no identifier is given, we try to render a decent one
            elif not ident:
                if 'email' in user_dict:
                    ident = user_dict['email']
                elif 'full_name' in user_dict:
                    ident = user_dict['full_name']
                else:
                    ident = user_dict.values()[0]

            # check for an existing user
            for attr_type in user_dict:
                attr_data = user_dict[attr_type]

                q = tbl_info.select(whereclause=(
                                    and_(tbl_info.c.attr_type == attr_type,
                                         tbl_info.c.attr_data == attr_data)))
                rows = conn.execute(q).fetchall()

                if rows:
                    log.msg("found existing User Object with attribute "
                            "%r: %r and uid %r" % (attr_type, attr_data,
                                                   rows[0].uid))
                    return rows[0].uid

            # insert new uid if needed
            if not uid:
                r = conn.execute(tbl.insert(), dict(identifier=ident))
                uid = r.inserted_primary_key[0]

            # update users table if type is null
            for attr in user_dict:
                if attr in self.known_types:
                    qs = tbl.select(whereclause=(tbl.c.uid == uid))
                    row = conn.execute(qs).fetchone()

                    qu = tbl.update(whereclause=(tbl.c.uid == uid))
                    if not row.full_name and attr == 'full_name':
                        conn.execute(qu, full_name=user_dict[attr])
                    if not row.email and attr == 'email':
                        conn.execute(qu, email=user_dict[attr])

            # add new attr_foo to users_info table
            for attr_type in user_dict:
                attr_data = user_dict[attr_type]
                if attr_type in self.known_info_types:
                    r = conn.execute(tbl_info.insert(),
                                     dict(uid=uid, attr_type=attr_type,
                                          attr_data=attr_data))

            log.msg("added User Object to table: %r" % user_dict)
            transaction.commit()
            return uid
        d = self.db.pool.do(thd)
        return d

    @base.cached("usdicts")
    def getUser(self, key):
        """
        Get a dictionary representing a given user, or None if no matching
        user is found.

        @param key: to work with the caching decorator, there can only be
                    one argument given to the method, which is either the
                    user id (uid) or the string used as index if uid is not
                    known (identifier)
        @type key: int or string

        @param no_cache: bypass cache and always fetch from database
        @type no_cache: boolean

        @returns: User dictionary via deferred
        """
        def thd(conn):
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info
            q = None

            if isinstance(key, int):
                q = tbl.select(whereclause=(tbl.c.uid == key))
            elif key:
                q = tbl.select(whereclause=(tbl.c.identifier == key))
            else:
                return None

            row = conn.execute(q).fetchone()

            if not row:
                return None

            # make UsDict to return
            usdict = UsDict()
            usdict['uid'] = row.uid
            usdict['identifier'] = row.identifier
            usdict['full_name'] = row.full_name
            usdict['email'] = row.email

            # gather all attr_type and attr_data entries from users_info table
            q = tbl_info.select(whereclause=(tbl_info.c.uid == usdict['uid']))
            rows = conn.execute(q).fetchall()

            for row in rows:
                usdict[row.attr_type] = row.attr_data

            log.msg("got User Object from table: %r" % usdict)
            return usdict
        d = self.db.pool.do(thd)
        return d

    def updateUser(self, uid=None, identifier=None, user_dict=None):
        """Updates a user's attributes in the database with the given user_dict
        items. Returns a deferred or None if there is no matching user found.
        If an item is in user_dict that a matching user does not have yet, that
        item will be added to the tables.

        @param uid: user id number
        @type uid: int

        @param identifier: string used as index if uid is not known
        @type identifier: string

        @param user_dict: dictionary whose key/value pairs are attr_type
                          and attr_data pairs
        @type user_dict: dictionary

        @returns: Deferred or None
        """

        def thd(conn):
            if not user_dict:
                return None
            transaction = conn.begin()

            tbl = self.db.model.users
            tbl_info = self.db.model.users_info

            if uid:
                q = tbl.select(whereclause=(tbl.c.uid == uid))
            elif identifier:
                q = tbl.select(whereclause=(tbl.c.identifier == identifier))
            else:
                return None

            # if no matching user is found, return
            row = conn.execute(q).fetchone()
            if not row:
                return None

            row_uid = row.uid
            qs = tbl_info.select(whereclause=(tbl_info.c.uid == row_uid))
            rows = conn.execute(qs).fetchall()
            if not rows:
                rows = []

            for attr_type in user_dict:
                attr_data = user_dict[attr_type]

                # update value if attr_type exists, otherwise add a new row
                if attr_type in self.known_types:
                    qu = tbl.update(whereclause=(tbl.c.uid == row_uid))
                    if row.full_name and attr_type == 'full_name':
                        conn.execute(qu, full_name=user_dict[attr_type])
                    if row.email and attr_type == 'email':
                        conn.execute(qu, email=user_dict[attr_type])

                elif attr_type in self.known_info_types:
                    for info_row in rows:
                        if info_row.attr_type == attr_type:
                            qu = tbl_info.update(whereclause=(
                                    and_(tbl_info.c.attr_type == attr_type,
                                         tbl_info.c.uid == info_row_uid)))
                            conn.execute(qu, attr_data=attr_data)
                            break
                    else:
                        if attr_type in self.known_info_types:
                            conn.execute(tbl_info.insert(),
                                         dict(uid=row_uid,
                                              attr_type=attr_type,
                                              attr_data=attr_data))
            transaction.commit()
            log.msg("updated following attributes of matching User Object in "
                    "table: %r" % user_dict)
        d = self.db.pool.do(thd)
        return d

    def removeUser(self, uid=None, identifier=None):
        """
        Remove a user with the given uid from the database, returns a UsDict
        with the removed user via Deferred if the user was found.

        @param uid: unique user id number
        @type uid: int

        @param identifier: string used as index if uid is not known
        @type identifier: string

        @returns: UsDict via Deferred
        """

        def thd(conn):
            tbl = self.db.model.users
            tbl_info = self.db.model.users_info

            if uid:
                q = tbl.select(whereclause=(tbl.c.uid == uid))
            elif identifier:
                q = tbl.select(whereclause=(tbl.c.identifier == identifier))
            else:
                return None

            res = conn.execute(q)
            row = res.fetchone()

            if not row:
                return None

            qs = tbl_info.select(whereclause=(tbl_info.c.uid == row.uid))
            info_rows = conn.execute(qs).fetchall()

            conn.execute(tbl_info.delete(whereclause=(tbl_info.c.uid == row.uid)))
            conn.execute(tbl.delete(whereclause=(tbl.c.uid == row.uid)))

            # gather all attr_type and attr_data entries
            usdict = {}
            usdict['uid'] = row.uid
            usdict['identifier'] = row.identifier
            usdict['full_name'] = row.full_name
            usdict['email'] = row.email

            for row in info_rows:
                usdict[row.attr_type] = row.attr_data
            log.msg("removed User Object from table: %r" % usdict)
            return usdict
        d = self.db.pool.do(thd)
        return d
