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

import sqlalchemy as sa
from twisted.trial import unittest
from twisted.internet import defer, task
from buildbot.db import users
from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb

class TestUsersConnectorComponent(connector_component.ConnectorComponentMixin,
                                 unittest.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(table_names=['users'])
        def finish_setup(_):
            self.db.users = users.UsersConnectorComponent(self.db)
        d.addCallback(finish_setup)

        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # sample user data

    user1_rows = [
        fakedb.User(id=1, uid=1, auth_type='full_name', auth_data='tyler durden'),
        fakedb.User(id=2, uid=1)
    ]

    user1_without_email = [
        fakedb.User(id=1, uid=1, auth_type='full_name', auth_data='tyler durden')
    ]

    user2_rows = [
        fakedb.User(id=1, uid=1, auth_type='username', auth_data='tdurden'),
        fakedb.User(id=2, uid=1, auth_type='password', auth_data='lye'),
    ]

    user1_dict = {
        'uid': 1,
        'identifier': u'soap',
        'full_name': u'tyler durden',
        'email': u'tyler@mayhem.net'
    }

    # updated email
    user1_updated_dict = {
        'uid': 1,
        'identifier': u'soap',
        'full_name': u'tyler durden',
        'email': u'narrator@mayhem.net'
    }

    user2_dict = {
        'uid': 1,
        'identifier': u'tdurden',
        'username': u'tdurden',
        'password': u'lye'
    }

    # tests

    def test_addUser(self):
        d = self.db.users.addUser(identifier='soap',
                                  auth_dict={'full_name': 'tyler durden',
                                             'email': 'tyler@mayhem.net'})
        def check_user(uid):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0].id, 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'soap')
                self.assertEqual(rows[0].auth_type, 'email')
                self.assertEqual(rows[0].auth_data, 'tyler@mayhem.net')
                self.assertEqual(rows[1].id, 2)
                self.assertEqual(rows[1].uid, 1)
                self.assertEqual(rows[1].identifier, 'soap')
                self.assertEqual(rows[1].auth_type, 'full_name')
                self.assertEqual(rows[1].auth_data, 'tyler durden')
            return self.db.pool.do(thd)
        d.addCallback(check_user)
        return d

    def test_addUser_existing_identifier(self):
        d = self.db.users.addUser(identifier='soap',
                                  auth_dict={'full_name': 'tyler durden',
                                             'email': 'tyler@mayhem.net'})
        d.addCallback(lambda _ : self.db.users.addUser(
                                            identifier='soap',
                                            auth_dict={'nick': 'narrator'}))
        def check_user(uid):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 3)
                self.assertEqual(rows[0].id, 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'soap')
                self.assertEqual(rows[0].auth_type, 'email')
                self.assertEqual(rows[0].auth_data, 'tyler@mayhem.net')
                self.assertEqual(rows[1].id, 2)
                self.assertEqual(rows[1].uid, 1)
                self.assertEqual(rows[1].identifier, 'soap')
                self.assertEqual(rows[1].auth_type, 'full_name')
                self.assertEqual(rows[1].auth_data, 'tyler durden')
                self.assertEqual(rows[2].id, 3)
                self.assertEqual(rows[2].uid, 1)
                self.assertEqual(rows[2].identifier, 'soap')
                self.assertEqual(rows[2].auth_type, 'nick')
                self.assertEqual(rows[2].auth_data, 'narrator')
            return self.db.pool.do(thd)
        d.addCallback(check_user)
        return d

    def test_addUser_merge_on_email(self):
        d = self.db.users.addUser(identifier='soap',
                                  auth_dict={'full_name': 'tyler durden',
                                             'email': 'tyler@mayhem.net'})
        d.addCallback(lambda _ : self.db.users.addUser(
                                            auth_dict={'username': 'tyler'}))
        def check_user(uid):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 3)
                self.assertEqual(rows[0].id, 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'soap')
                self.assertEqual(rows[0].auth_type, 'email')
                self.assertEqual(rows[0].auth_data, 'tyler@mayhem.net')
                self.assertEqual(rows[1].id, 2)
                self.assertEqual(rows[1].uid, 1)
                self.assertEqual(rows[1].identifier, 'soap')
                self.assertEqual(rows[1].auth_type, 'full_name')
                self.assertEqual(rows[1].auth_data, 'tyler durden')
                self.assertEqual(rows[2].id, 3)
                self.assertEqual(rows[2].uid, 1)
                self.assertEqual(rows[2].identifier, 'soap')
                self.assertEqual(rows[2].auth_type, 'username')
                self.assertEqual(rows[2].auth_data, 'tyler')
            return self.db.pool.do(thd)
        d.addCallback(check_user)
        return d

    def test_addUser_merge_on_username(self):
        d = self.db.users.addUser(identifier='soap',
                                  auth_dict={'full_name': 'tyler durden',
                                             'username': 'tyler'})
        d.addCallback(lambda _ : self.db.users.addUser(
                                    auth_dict={'email': 'tyler@mayhem.net'}))
        def check_user(uid):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 3)
                self.assertEqual(rows[0].id, 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'soap')
                self.assertEqual(rows[0].auth_type, 'username')
                self.assertEqual(rows[0].auth_data, 'tyler')
                self.assertEqual(rows[1].id, 2)
                self.assertEqual(rows[1].uid, 1)
                self.assertEqual(rows[1].identifier, 'soap')
                self.assertEqual(rows[1].auth_type, 'full_name')
                self.assertEqual(rows[1].auth_data, 'tyler durden')
                self.assertEqual(rows[2].id, 3)
                self.assertEqual(rows[2].uid, 1)
                self.assertEqual(rows[2].identifier, 'soap')
                self.assertEqual(rows[2].auth_type, 'email')
                self.assertEqual(rows[2].auth_data, 'tyler@mayhem.net')
            return self.db.pool.do(thd)
        d.addCallback(check_user)
        return d

    def test_getUser_uid(self):
        d = self.insertTestData(self.user1_rows)
        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)
        def check1(usdict):
            self.assertEqual(usdict, self.user1_dict)
        d.addCallback(check1)
        return d

    def test_getUser_identifier(self):
        d = self.insertTestData(self.user1_rows)
        def get1(_):
            return self.db.users.getUser('soap')
        d.addCallback(get1)
        def check1(usdict):
            self.assertEqual(usdict, self.user1_dict)
        d.addCallback(check1)
        return d

    def test_getNoMatch(self):
        d = self.insertTestData(self.user1_rows)
        def get3(_):
            return self.db.users.getUser(3)
        d.addCallback(get3)
        def check3(none):
            self.assertEqual(none, None)
        d.addCallback(check3)
        return d

    def test_updateUser_existing_type(self):
        d = self.insertTestData(self.user1_rows)
        def update1(_):
            return self.db.users.updateUser(
                uid=1, auth_dict={'email': 'narrator@mayhem.net'})
        d.addCallback(update1)
        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)
        def check1(usdict):
            self.assertEqual(usdict, self.user1_updated_dict)
        d.addCallback(check1)
        return d

    def test_updateUser_new_type_uid(self):
        d = self.insertTestData(self.user1_rows)
        def update1(_):
            return self.db.users.updateUser(uid=1, auth_dict={'sekret': 'jack'})
        d.addCallback(update1)
        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)
        def check1(usdict):
            newdict = self.user1_dict
            newdict['sekret'] = 'jack'
            self.assertEqual(usdict, newdict)
        d.addCallback(check1)
        return d

    def test_updateUser_new_type_identifier(self):
        d = self.insertTestData(self.user1_rows)
        def update1(_):
            return self.db.users.updateUser(identifier='soap',
                                            auth_dict={'sekret': 'jack'})
        d.addCallback(update1)
        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)
        def check1(usdict):
            newdict = self.user1_dict
            newdict['sekret'] = 'jack'
            self.assertEqual(usdict, newdict)
        d.addCallback(check1)
        return d

    def test_updateNoMatch(self):
        d = self.insertTestData(self.user1_rows)
        def update3(_):
            return self.db.users.updateUser(
                uid=3, auth_dict={'email': 'narrator@mayhem.net'})
        d.addCallback(update3)
        def check3(none):
            self.assertEqual(none, None)
        d.addCallback(check3)
        return d

    def test_removeUser_uid(self):
        d = self.insertTestData(self.user1_rows)
        def remove1(_):
            return self.db.users.removeUser(uid=1)
        d.addCallback(remove1)
        def check1(removed):
            self.assertEqual(removed, self.user1_dict)
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                r = r.fetchall()
                self.assertEqual(len(r), 0)
            return self.db.pool.do(thd)
        d.addCallback(check1)
        return d

    def test_removeUser_identifier(self):
        d = self.insertTestData(self.user1_rows)
        def remove1(_):
            return self.db.users.removeUser(identifier='soap')
        d.addCallback(remove1)
        def check1(removed):
            self.assertEqual(removed, self.user1_dict)
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                r = r.fetchall()
                self.assertEqual(len(r), 0)
            return self.db.pool.do(thd)
        d.addCallback(check1)
        return d

    def test_removeNoMatch(self):
        d = self.insertTestData(self.user1_rows)
        def remove1(_):
            return self.db.users.removeUser(uid=3)
        d.addCallback(remove1)
        def check1(removed):
            self.assertEqual(removed, None)
        d.addCallback(check1)
        return d

    def test_checkFromGit_both_in_table(self):
        d = self.insertTestData(self.user1_rows)
        def test_check(_):
            user = dict(full_name='tyler durden', email='tyler@mayhem.net')
            return self.db.users.checkFromGit(user)
        d.addCallback(test_check)
        def check_check(uid):
            def thd(conn):
                self.assertEqual(uid, 1)
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0].id, 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'soap')
                self.assertEqual(rows[0].auth_type, 'full_name')
                self.assertEqual(rows[0].auth_data, 'tyler durden')
                self.assertEqual(rows[1].id, 2)
                self.assertEqual(rows[1].uid, 1)
                self.assertEqual(rows[1].identifier, 'soap')
                self.assertEqual(rows[1].auth_type, 'email')
                self.assertEqual(rows[1].auth_data, 'tyler@mayhem.net')
            return self.db.pool.do(thd)
        d.addCallback(check_check)
        return d

    def test_checkFromGit_merge_on_username(self):
        d = self.db.users.addUser(identifier='soap',
                                  auth_dict={'username': 'tdurden',
                                             'password': 'lye'})
        def test_check(_):
            user = dict(full_name='tyler durden', email='tdurden@mayhem.net')
            return self.db.users.checkFromGit(user)
        d.addCallback(test_check)
        def check_check(uid):
            def thd(conn):
                self.assertEqual(uid, 1)
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 4)
                self.assertEqual(rows[0].id, 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'soap')
                self.assertEqual(rows[0].auth_type, 'username')
                self.assertEqual(rows[0].auth_data, 'tdurden')
                self.assertEqual(rows[1].id, 2)
                self.assertEqual(rows[1].uid, 1)
                self.assertEqual(rows[1].identifier, 'soap')
                self.assertEqual(rows[1].auth_type, 'password')
                self.assertEqual(rows[1].auth_data, 'lye')
                self.assertEqual(rows[2].id, 3)
                self.assertEqual(rows[2].uid, 1)
                self.assertEqual(rows[2].identifier, 'soap')
                self.assertEqual(rows[2].auth_type, 'email')
                self.assertEqual(rows[2].auth_data, 'tdurden@mayhem.net')
                self.assertEqual(rows[3].id, 4)
                self.assertEqual(rows[3].uid, 1)
                self.assertEqual(rows[3].identifier, 'soap')
                self.assertEqual(rows[3].auth_type, 'full_name')
                self.assertEqual(rows[3].auth_data, 'tyler durden')
            return self.db.pool.do(thd)
        d.addCallback(check_check)
        return d

    def test_checkFromGit_full_name_in_table(self):
        d = self.insertTestData(self.user1_without_email)
        def test_check(_):
            user = dict(full_name='tyler durden', email=None)
            return self.db.users.checkFromGit(user)
        d.addCallback(test_check)
        def check_check(uid):
            def thd(conn):
                self.assertEqual(uid, 1)
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0].id, 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'soap')
                self.assertEqual(rows[0].auth_type, 'full_name')
                self.assertEqual(rows[0].auth_data, 'tyler durden')
            return self.db.pool.do(thd)
        d.addCallback(check_check)
        return d

    def test_checkFromGit_not_in_table(self):
        def test_check():
            user = dict(full_name='tyler durden', email='tyler@mayhem.net')
            return self.db.users.checkFromGit(user)
        d = test_check()
        def check_check(uid):
            def thd(conn):
                self.assertEqual(uid, 1)
                r = conn.execute(self.db.model.users.select())
                rows = r.fetchall()
                self.assertEqual(len(rows), 2)
                self.assertEqual(rows[0].id, 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'tyler durden')
                self.assertEqual(rows[0].auth_type, 'email')
                self.assertEqual(rows[0].auth_data, 'tyler@mayhem.net')
                self.assertEqual(rows[1].id, 2)
                self.assertEqual(rows[1].uid, 1)
                self.assertEqual(rows[1].identifier, 'tyler durden')
                self.assertEqual(rows[1].auth_type, 'full_name')
                self.assertEqual(rows[1].auth_data, 'tyler durden')
            return self.db.pool.do(thd)
        d.addCallback(check_check)
        return d
