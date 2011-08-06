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

from twisted.trial import unittest
from buildbot.db import users
from buildbot.test.util import connector_component
from buildbot.test.fake import fakedb

class TestUsersConnectorComponent(connector_component.ConnectorComponentMixin,
                                 unittest.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(table_names=['users', 'users_info'])
        def finish_setup(_):
            self.db.users = users.UsersConnectorComponent(self.db)
        d.addCallback(finish_setup)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # sample user data

    user1_rows = [
        fakedb.User(uid=1, identifier='soap', full_name='Tyler Durden',
                    email='tyler@mayhem.net'),
        fakedb.UserInfo(uid=1)
    ]

    user2_rows = [
        fakedb.User(uid=2),
        fakedb.UserInfo(uid=2, attr_type='authz_user', attr_data='tdurden'),
        fakedb.UserInfo(uid=2, attr_type='authz_pass', attr_data='lye')
    ]

    user1_dict = {
        'uid': 1,
        'identifier': u'soap',
        'full_name': u'Tyler Durden',
        'email': u'tyler@mayhem.net',
        'git': u'Tyler Durden <tyler@mayhem.net>'
    }

    # updated email
    user1_updated_dict = {
        'uid': 1,
        'identifier': u'soap',
        'full_name': u'Tyler Durden',
        'email': u'narrator@mayhem.net',
        'git': u'Tyler Durden <tyler@mayhem.net>'
    }

    user2_dict = {
        'uid': 2,
        'identifier': u'tdurden',
        'authz_user': u'tdurden',
        'authz_pass': u'lye'
    }

    # tests

    def test_addUser(self):
        d = self.db.users.addUser(user_dict={'full_name': 'tyler durden',
                                             'email': 'tyler@mayhem.net',
                                             'authz_user': 'tdurden',
                                             'authz_pass': 'lye'})
        def check_user(uid):
            self.assertEqual(uid, 1)
            def thd(conn):
                rows = conn.execute(self.db.model.users.select()).fetchall()
                infos = conn.execute(self.db.model.users_info.select()).fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'tyler@mayhem.net')
                self.assertEqual(rows[0].full_name, 'tyler durden')
                self.assertEqual(rows[0].email, 'tyler@mayhem.net')
                self.assertEqual(len(infos), 2)
                self.assertEqual(infos[0].uid, 1)
                self.assertEqual(infos[0].attr_type, 'authz_user')
                self.assertEqual(infos[0].attr_data, 'tdurden')
                self.assertEqual(infos[1].uid, 1)
                self.assertEqual(infos[1].attr_type, 'authz_pass')
                self.assertEqual(infos[1].attr_data, 'lye')
            return self.db.pool.do(thd)
        d.addCallback(check_user)
        return d

    def test_addUser_existing_identifier(self):
        d = self.db.users.addUser(identifier='soap',
                                  user_dict={'authz_user': 'tdurden'})
        d.addCallback(lambda _ : self.db.users.addUser(
                                            identifier='soap',
                                            user_dict={'authz_pass': 'lye'}))
        def check_user(uid):
            self.assertEqual(uid, 1)
            def thd(conn):
                rows = conn.execute(self.db.model.users.select()).fetchall()
                infos = conn.execute(self.db.model.users_info.select()).fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'soap')
                self.assertEqual(rows[0].full_name, None)
                self.assertEqual(rows[0].email, None)
                self.assertEqual(len(infos), 2)
                self.assertEqual(infos[0].uid, 1)
                self.assertEqual(infos[0].attr_type, 'authz_user')
                self.assertEqual(infos[0].attr_data, 'tdurden')
                self.assertEqual(infos[1].uid, 1)
                self.assertEqual(infos[1].attr_type, 'authz_pass')
                self.assertEqual(infos[1].attr_data, 'lye')
            return self.db.pool.do(thd)
        d.addCallback(check_user)
        return d

    def test_addUser_existing_attr(self):
        d = self.db.users.addUser(identifier='soap',
                                  user_dict={'authz_user': 'tdurden'})
        d.addCallback(lambda _ : self.db.users.addUser(
                                            identifier='soap',
                                            user_dict={'authz_user': 'tdurden'}))
        def check_user(uid):
            self.assertEqual(uid, 1)
            def thd(conn):
                rows = conn.execute(self.db.model.users.select()).fetchall()
                infos = conn.execute(self.db.model.users_info.select()).fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0].uid, 1)
                self.assertEqual(rows[0].identifier, 'soap')
                self.assertEqual(rows[0].full_name, None)
                self.assertEqual(rows[0].email, None)
                self.assertEqual(len(infos), 1)
                self.assertEqual(infos[0].uid, 1)
                self.assertEqual(infos[0].attr_type, 'authz_user')
                self.assertEqual(infos[0].attr_data, 'tdurden')
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
                uid=1, user_dict={'email': 'narrator@mayhem.net'})
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
            return self.db.users.updateUser(uid=1, user_dict={'authz_user': 'jack'})
        d.addCallback(update1)
        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)
        def check1(usdict):
            newdict = self.user1_dict
            newdict['authz_user'] = 'jack'
            self.assertEqual(usdict, newdict)
        d.addCallback(check1)
        return d

    def test_updateUser_new_type_identifier(self):
        d = self.insertTestData(self.user1_rows)
        def update1(_):
            return self.db.users.updateUser(identifier='soap',
                                            user_dict={'authz_user': 'jack'})
        d.addCallback(update1)
        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)
        def check1(usdict):
            newdict = self.user1_dict
            newdict['authz_user'] = 'jack'
            self.assertEqual(usdict, newdict)
        d.addCallback(check1)
        return d

    def test_updateNoMatch(self):
        d = self.insertTestData(self.user1_rows)
        def update3(_):
            return self.db.users.updateUser(
                uid=3, user_dict={'email': 'narrator@mayhem.net'})
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
