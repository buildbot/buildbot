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

    Currently known auth_types:
        username, password, full_name, email
    """

    def addUser(self, identifier=None, auth_dict=None):
        """Adds a User to the database with the passed in attributes; returns
        the new user's uid via deferred. All arguments are keyword arguments.

        Note that a few merging techniques are applied to find an existing
        user before adding a new one. If the auth_dict contains an email
        address, the table is searched for usernames that match the local
        part of the email address. If the auth_dict contains a username,
        the table is searched for local parts of emails that match. Either
        way, if a match is found, the auth_dict items are added to the
        existing user.

        @param identifier: string used as index if uid is not known
        @type identifier: string

        @param auth_dict: dictionary whose key/value pairs are auth_type
                          and auth_data pairs
        @type auth_dict: dictionary

        @returns: new user's uid via Deferred or None
        """

        def thd(conn):
            if not auth_dict:
                return None

            transaction = conn.begin()
            tbl = self.db.model.users
            uid = None
            ident = None
            merged = False

            # if there's an email in the table that matches the new username
            # we merge the incoming auth_dict with the existing user
            if 'username' in auth_dict:
                res = conn.execute(
                    tbl.select(whereclause=(
                            and_(tbl.c.auth_type == 'email',
                                 tbl.c.auth_data.startswith(
                                    auth_dict['username'] + "@")))))
                rows = res.fetchall()

                if rows:
                    log.msg("adding to existing User Object with "
                            "email %r" % rows[0].auth_data)
                    uid = rows[0].uid
                    ident = rows[0].identifier
                    merged = True

            # if the username portion of an email is already stored as
            # a username, merge the new auth_dict with the existing user
            if 'email' in auth_dict and not merged:
                username = auth_dict['email'].split('@')[0]
                res = conn.execute(tbl.select(
                        whereclause=(and_(tbl.c.auth_type == 'username',
                                          tbl.c.auth_data == username))))
                rows = res.fetchall()

                if rows:
                    log.msg("adding to existing User Object with "
                            "username %r" % username)
                    uid = rows[0].uid
                    ident = rows[0].identifier
                    merged = True

            # if there's a user with the same identifier already in the
            # database, we use the existing uid
            if not merged:
                res = conn.execute(tbl.select(whereclause=(
                                      tbl.c.identifier == identifier)))
                rows = res.fetchall()
                if rows:
                    uid = rows[0].uid
                    ident = identifier

            if not ident:
                ident = identifier

            # begin inserting data
            for auth_type in auth_dict:
                auth_data = auth_dict[auth_type]

                r = conn.execute(tbl.insert(), dict(
                        identifier=ident,
                        auth_type=auth_type,
                        auth_data=auth_data))
                row_id = r.inserted_primary_key[0]

                # set user id to first primary key from inserting auth_dict
                if uid is None:
                    uid = row_id

                r = conn.execute(tbl.update(tbl.c.id == row_id), uid=uid)

            transaction.commit()
            log.msg("added User Object to table: %r" % auth_dict)
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
            uid, identifier = None, None
            if isinstance(key, int):
                uid = key
            else:
                identifier = key

            tbl = self.db.model.users
            q = None
            if uid:
                q = tbl.select(whereclause=(tbl.c.uid == uid))
            elif identifier:
                q = tbl.select(whereclause=(tbl.c.identifier == identifier))
            else:
                return None

            res = conn.execute(q)
            rows = res.fetchall()

            if not rows:
                return None

            # gather all auth_type and auth_data entries
            usdict = UsDict()
            usdict['uid'] = rows[0].uid
            usdict['identifier'] = rows[0].identifier
            for row in rows:
                usdict[row.auth_type] = row.auth_data
            log.msg("got User Object from table: %r" % usdict)
            return usdict
        d = self.db.pool.do(thd)
        return d
            
    def updateUser(self, uid=None, identifier=None, auth_dict=None):
        """Updates a user's attributes in the database with the given auth_dict
        items. Returns a deferred or None if there is no matching user found.
        If an item is in auth_dict that a matching user does not have yet, that
        item will be added to the table.

        @param uid: user id number
        @type uid: int

        @param identifier: string used as index if uid is not known
        @type identifier: string

        @param auth_dict: dictionary whose key/value pairs are auth_type
                          and auth_data pairs
        @type auth_dict: dictionary

        @returns: Deferred or None
        """

        def thd(conn):
            if not auth_dict:
                return None
            transaction = conn.begin()

            tbl = self.db.model.users

            if uid:
                q = tbl.select(whereclause=(tbl.c.uid == uid))
            elif identifier:
                q = tbl.select(whereclause=(tbl.c.identifier == identifier))
            else:
                return None

            # if no matching user is found, return
            rows = conn.execute(q).fetchall()
            if not rows:
                return None

            row_uid = rows[0].uid
            row_identifier = rows[0].identifier
            for auth_type in auth_dict:
                auth_data = auth_dict[auth_type]

                # update value if auth_type exists, otherwise add a new row
                for row in rows:
                    if row.auth_type == auth_type:
                        if uid:
                            qu = tbl.update(whereclause=(
                                    and_(tbl.c.auth_type == auth_type,
                                         tbl.c.uid == uid)))
                            conn.execute(qu, auth_data=auth_data)
                        else:
                            qu = tbl.update(whereclause=(
                                    and_(tbl.c.auth_type == auth_type,
                                         tbl.c.identifier == identifier)))
                            conn.execute(qu, auth_data=auth_data)
                        break
                else:
                    conn.execute(tbl.insert(), dict(uid=row_uid,
                                                    identifier=row_identifier,
                                                    auth_type=auth_type,
                                                    auth_data=auth_data))
            transaction.commit()
            log.msg("updated following attributes of matching User Objects in "
                    "table: %r" % auth_dict)
        d = self.db.pool.do(thd)
        return d

    def removeUser(self, uid=None, identifier=None):
        """
        Remove a user with the given uid from the database, returns a boolean
        via Deferred indicating if the user was found and removed or not found.

        @param uid: unique user id number
        @type uid: int

        @param identifier: string used as index if uid is not known
        @type identifier: string

        @returns: boolean via Deferred
        """

        def thd(conn):
            tbl = self.db.model.users            
            if uid:
                q = tbl.select(whereclause=(tbl.c.uid == uid))
            elif identifier:
                q = tbl.select(whereclause=(tbl.c.identifier == identifier))
            else:
                return False

            res = conn.execute(q)
            rows = res.fetchall()
            
            if not rows:
                return None

            if uid:
                conn.execute(tbl.delete(whereclause=(tbl.c.uid == uid)))
            else:
                conn.execute(tbl.delete(whereclause=(
                                        tbl.c.identifier == identifier)))

            # gather all auth_type and auth_data entries
            usdict = {}
            usdict['uid'] = rows[0].uid
            usdict['identifier'] = rows[0].identifier
            for row in rows:
                usdict[row.auth_type] = row.auth_data
            log.msg("removed User Object from table: %r" % usdict)
            return usdict
        d = self.db.pool.do(thd)
        return d

    def checkFromGit(self, user):
        """
        Take a parsed author from a git change and add the author to the
        database if they don't already exist, returning the new user id.

        Note that full_name may not be an existing user's identifier if
        that user was previously added through authz. Here, full_name is
        only set as the identifier when adding a new user, so we don't
        have to worry about overwriting the identifier set in checkFromAuthz.

        A few merging techniques are applied to find an existing user before
        adding a new one. If the user contains an email address, the table is
        searched for usernames that match the local part of the email address.
        If a match is found, the auth_dict items are added to the existing
        user.

        @param user: parsed author from a git change
        @type user: dictionary

        @returns: user id or None via deferred
        """

        def thd(conn):
            tbl = self.db.model.users
            auth_dict = {}
            has_email = False

            # on git commits, the default identifier is set to full_name
            identifier = user['full_name']

            if user['email']:
                has_email = True
                auth_dict['email'] = user['email']
                auth_dict['full_name'] = user['full_name']
                q = tbl.select(whereclause=(
                        or_(and_(tbl.c.auth_type == 'email',
                                 tbl.c.auth_data == user['email']),
                            and_(tbl.c.auth_type == 'full_name',
                                 tbl.c.auth_data == user['full_name']))))
            else:
                auth_dict['full_name'] = user['full_name']
                q = tbl.select(whereclause=(
                        and_(tbl.c.auth_type == 'full_name',
                            tbl.c.auth_data == user['full_name'])))
            res = conn.execute(q)
            row = res.fetchone()

            # if no match found, add one
            if not row:
                transaction = conn.begin()
                uid = None
                merged = False

                # if the username portion of an email is already stored as
                # a username, merge the new auth_dict with the existing user
                if has_email:
                    username = auth_dict['email'].split('@')[0]
                    res = conn.execute(tbl.select(
                            whereclause=(and_(tbl.c.auth_type == 'username',
                                              tbl.c.auth_data == username))))
                    rows = res.fetchall()

                    if rows:
                        log.msg("adding to existing User Object with "
                                "username %r" % username)
                        uid = rows[0].uid
                        identifier = rows[0].identifier
                        merged = True

                # if there's a user with the same identifier already in the
                # database, we use the existing uid
                if not merged:
                    res = conn.execute(tbl.select(whereclause=(
                                tbl.c.identifier == identifier)))
                    rows = res.fetchall()
                    if rows:
                        log.msg("adding to existing User Object with "
                                "identifier %r" % identifier)
                        uid = rows[0].uid

                for auth_type in auth_dict:
                    auth_data = auth_dict[auth_type]

                    r = conn.execute(tbl.insert(), dict(
                            identifier=identifier,
                            auth_type=auth_type,
                            auth_data=auth_data))
                    row_id = r.inserted_primary_key[0]

                    # set user id to first primary key from inserting auth_dict
                    if uid is None:
                        uid = row_id
                        log.msg("created new User Object with uid '%r' and "
                                "identifier %r" % (uid, identifier))
                    r = conn.execute(tbl.update(tbl.c.id == row_id), uid=uid)

                transaction.commit()
                return uid
            log.msg("found existing User Object with uid '%r' and "
                    "identifier %r" % (row.uid, row.identifier))
            return row.uid

        d = self.db.pool.do(thd)
        return d

    def checkFromAuthz(self, user):
        """
        Take a parsed username/password pair from status.web.auth and add
        them to the database if they don't already exist, returning the new
        user id.

        Note that the username identifier from authz takes precedence over
        the full_name identifier that is set in checkFromGit, and will
        overwrite the full_name identifier if found.

        A few merging techniques are applied to find an existing user before
        adding a new one. The user's username is used to check against existing
        local parts of email addresses stored in the table. If a match is found,
        the auth_dict items are added to the existing user.

        @param user: a username/password pair from status.web.auth
        @type user: tuple

        @returns: user id or None via deferred
        """

        def thd(conn):
            tbl = self.db.model.users
            auth_dict = {}

            # on authz, the default identifier is set to the username
            identifier = user['username']

            auth_dict['username'] = user['username']
            auth_dict['password'] = user['password']
            q = tbl.select(whereclause=(
                    or_(and_((tbl.c.auth_type == 'username'),
                             (tbl.c.auth_data == user['username'])),
                        and_((tbl.c.auth_type == 'password'),
                             (tbl.c.auth_data == user['password'])))))
            res = conn.execute(q)
            row = res.fetchone()

            # if no match found, add one
            if not row:
                transaction = conn.begin()
                uid = None
                merged = False

                # if there's an email in the table that matches the new username
                # we merge the incoming auth_dict with the existing user
                res = conn.execute(
                    tbl.select(whereclause=(
                            and_(tbl.c.auth_type == 'email',
                                 tbl.c.auth_data.startswith(
                                    auth_dict['username'] + "@")))))
                rows = res.fetchall()

                if rows:
                    log.msg("adding to existing User Object with "
                            "email %r" % rows[0].auth_data)
                    uid = rows[0].uid
                    identifier = rows[0].identifier
                    merged = True

                # if there's a user with the same identifier already in the
                # database, we use the existing uid
                if not merged:
                    res = conn.execute(tbl.select(whereclause=(
                                           tbl.c.identifier == identifier)))
                    rows = res.fetchall()

                    if rows:
                        log.msg("adding to existing User Object with "
                                "identifier %r" % identifier)
                        uid = rows[0].uid

                for auth_type in auth_dict:
                    auth_data = auth_dict[auth_type]

                    r = conn.execute(tbl.insert(), dict(
                            identifier=identifier,
                            auth_type=auth_type,
                            auth_data=auth_data))
                    row_id = r.inserted_primary_key[0]

                    # set user id to first primary key from inserting auth_dict
                    if uid is None:
                        log.msg("created new User Object with uid '%r' and "
                                "identifier %r" % (uid, identifier))
                        uid = row_id
                    r = conn.execute(tbl.update(tbl.c.id == row_id), uid=uid)

                transaction.commit()
                return uid

            if user['username'] != row.identifier:
                r = conn.execute(tbl.update(tbl.c.identifier == row.identifier),
                                 identifier=identifier)
            log.msg("found existing User Object with uid '%r' and "
                    "identifier %r" % (row.uid, row.identifier))
            return row.uid

        d = self.db.pool.do(thd)
        return d
