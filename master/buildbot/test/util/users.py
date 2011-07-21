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

import mock
from twisted.internet import defer

from buildbot.test.fake import fakedb
from buildbot.process.users import users

class ManualUsersMixin(object):
    """
    This class fakes out the master/db components to test the manual
    user managers located in process.users.manual.
    """

    class FakeMaster(object):

        def __init__(self):
            self.db = fakedb.FakeDBConnector(self)
            self.slavePortnum = 9989
            self.caches = mock.Mock(name="caches")
            self.caches.get_cache = self.get_cache

        def get_cache(self, cache_name, miss_fn):
            c = mock.Mock(name=cache_name)
            c.get = miss_fn
            return c

    def setUpManualUsers(self):
        pass

    def tearDownManualUsers(self):
        pass

    def attachManualUsers(self, manual_component):
        self.master = self.FakeMaster()
        manual_component.master = self.master
        return manual_component

class UsersMixin(object):
    """
    This class is used for testing user components, faking out parts of
    buildbot.process.users that other tests need
    """

    stored_users = None
    next_id = 1

    def setUpUsers(self):
        self.stored_users = []

    def createUserObject(self, names, src=None):
        if src == "git":
            d = users.parseGitAuthor(names)
            d.addCallback(lambda usdict : self.checkFromGit(usdict))
            return d
        elif src == "authz":
            d = users.parseAuthz(names)
            def check_authz(usdict):
                if usdict:
                    return self.checkFromAuthz(usdict)
            d.addCallback(check_authz)
            return d

    def checkFromGit(self, usdict):
        res = None
        auth_dict = {}
        identifier = usdict['full_name']

        if usdict['email']:
            auth_dict['email'] = usdict['email']
            auth_dict['full_name'] = usdict['full_name']
            for row in self.stored_users:
                if (row['auth_type'] == 'email' and
                    row['auth_data'] == usdict['email']) or \
                   (row['auth_type'] == 'full_name' and
                    row['auth_data'] == usdict['full_name']):
                   res = row
        else:
            auth_dict['full_name'] = usdict['full_name']
            for row in self.stored_users:
                if row['auth_type'] == 'full_name' and \
                   row['auth_data'] == usdict['full_name']:
                    res = row

        r_uid = None
        if not res:
            uid = None
            for auth_type in auth_dict:
                auth_data = auth_dict[auth_type]
                self.stored_users.append(dict(id=self.next_id,
                                             identifier=identifier,
                                             auth_type=auth_type,
                                             auth_data=auth_data))
                if uid is None:
                    r_uid = uid = self.next_id

                self.stored_users[-1].update(dict(uid=uid))
                self.next_id += self.next_id
        else:
            r_uid = res['uid']
        return defer.succeed(r_uid)

    def checkFromAuthz(self, usdict):
        res = None
        auth_dict = {}
        identifier = usdict['username']

        auth_dict['username'] = usdict['username']
        auth_dict['password'] = usdict['password']
        for row in self.stored_users:
            if (row['auth_type'] == 'username' and
                row['auth_data'] == usdict['username']) or \
                (row['auth_type'] == 'password' and
                 row['auth_data'] == usdict['password']):
                res = row

        r_uid = None
        if not res:
            uid = None
            for auth_type in auth_dict:
                auth_data = auth_dict[auth_type]
                self.stored_users.append(dict(id=self.next_id,
                                             identifier=identifier,
                                             auth_type=auth_type,
                                             auth_data=auth_data))
                if uid is None:
                    r_uid = uid = self.next_id

                self.stored_users[-1].update(dict(uid=uid))
                self.next_id += self.next_id
        else:
            r_uid = res['uid']
        return defer.succeed(r_uid)

    def getUserContact(self, contact_type=None, uid=None):
        contact = None
        res = None
        for row in self.stored_users:
            if row['uid'] == uid:
                res = row

        if res and contact_type in res:
            contact = res[contact_type]
        return defer.succeed(contact)

    def perspective_commandline(self, op, ids, info):
        results = []
        if ids:
            for user in ids:
                r = None
                if op == 'remove':
                    for elem in self.stored_users:
                        if user == elem['identifier']:
                            r = self.stored_users.pop(self.stored_users.index(elem))
                elif op == 'show':
                    for elem in self.stored_users:
                        if user == elem['identifier']:
                            r = self.stored_users[self.stored_users.index(elem)]
                results.append(r)
        else:
            for user in info:
                r = None
                if op == 'add':
                    r = user['uid'] = self.next_id
                    self.stored_users.append(user)
                    self.next_id += self.next_id
                elif op == 'update':
                    for elem in self.stored_users:
                        if user['identifier'] == elem['identifier']:
                            for key in user:
                                elem[key] = user[key]
                results.append(r)
        return results
