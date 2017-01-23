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

import sqlalchemy

from twisted.trial import unittest

from buildbot.db import users
from buildbot.test.fake import fakedb
from buildbot.test.util import connector_component


class TestUsersConnectorComponent(connector_component.ConnectorComponentMixin,
                                  unittest.TestCase):

    def setUp(self):
        d = self.setUpConnectorComponent(
            table_names=['users', 'users_info', 'changes', 'change_users',
                         'sourcestamps', 'patches'])

        def finish_setup(_):
            self.db.users = users.UsersConnectorComponent(self.db)
        d.addCallback(finish_setup)
        return d

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # sample user data

    user1_rows = [
        fakedb.User(uid=1, identifier='soap'),
        fakedb.UserInfo(uid=1, attr_type='IPv9', attr_data='0578cc6.8db024'),
    ]

    user2_rows = [
        fakedb.User(uid=2, identifier='lye'),
        fakedb.UserInfo(uid=2, attr_type='git',
                        attr_data='Tyler Durden <tyler@mayhem.net>'),
        fakedb.UserInfo(uid=2, attr_type='irc', attr_data='durden')
    ]

    user3_rows = [
        fakedb.User(uid=3, identifier='marla', bb_username='marla',
                    bb_password='cancer')
    ]

    user1_dict = {
        'uid': 1,
        'identifier': u'soap',
        'bb_username': None,
        'bb_password': None,
        'IPv9': u'0578cc6.8db024',
    }

    user2_dict = {
        'uid': 2,
        'identifier': u'lye',
        'bb_username': None,
        'bb_password': None,
        'irc': u'durden',
        'git': u'Tyler Durden <tyler@mayhem.net>'
    }

    user3_dict = {
        'uid': 3,
        'identifier': u'marla',
        'bb_username': u'marla',
        'bb_password': u'cancer',
    }

    # tests

    def test_addUser_new(self):
        d = self.db.users.findUserByAttr(identifier='soap',
                                         attr_type='subspace_net_handle',
                                         attr_data='Durden0924')

        def check_user(uid):
            def thd(conn):
                users_tbl = self.db.model.users
                users_info_tbl = self.db.model.users_info
                users = conn.execute(users_tbl.select()).fetchall()
                infos = conn.execute(users_info_tbl.select()).fetchall()
                self.assertEqual(len(users), 1)
                self.assertEqual(users[0].uid, uid)
                self.assertEqual(users[0].identifier, 'soap')
                self.assertEqual(len(infos), 1)
                self.assertEqual(infos[0].uid, uid)
                self.assertEqual(infos[0].attr_type, 'subspace_net_handle')
                self.assertEqual(infos[0].attr_data, 'Durden0924')
            return self.db.pool.do(thd)
        d.addCallback(check_user)
        return d

    def test_addUser_existing(self):
        d = self.insertTestData(self.user1_rows)
        d.addCallback(lambda _: self.db.users.findUserByAttr(
            identifier='soapy',
            attr_type='IPv9',
            attr_data='0578cc6.8db024'))

        def check_user(uid):
            self.assertEqual(uid, 1)

            def thd(conn):
                users_tbl = self.db.model.users
                users_info_tbl = self.db.model.users_info
                users = conn.execute(users_tbl.select()).fetchall()
                infos = conn.execute(users_info_tbl.select()).fetchall()
                self.assertEqual(len(users), 1)
                self.assertEqual(users[0].uid, uid)
                self.assertEqual(users[0].identifier, 'soap')  # not changed!
                self.assertEqual(len(infos), 1)
                self.assertEqual(infos[0].uid, uid)
                self.assertEqual(infos[0].attr_type, 'IPv9')
                self.assertEqual(infos[0].attr_data, '0578cc6.8db024')
            return self.db.pool.do(thd)
        d.addCallback(check_user)
        return d

    def test_findUser_existing(self):
        d = self.insertTestData(
            self.user1_rows + self.user2_rows + self.user3_rows)
        d.addCallback(lambda _: self.db.users.findUserByAttr(
            identifier='lye',
            attr_type='git',
            attr_data='Tyler Durden <tyler@mayhem.net>'))

        def check_user(uid):
            self.assertEqual(uid, 2)

            def thd(conn):
                users_tbl = self.db.model.users
                users_info_tbl = self.db.model.users_info
                users = conn.execute(users_tbl.select()).fetchall()
                infos = conn.execute(users_info_tbl.select()).fetchall()
                self.assertEqual((
                    sorted([tuple(u) for u in users]),
                    sorted([tuple(i) for i in infos])
                ), (
                    [
                        (1, u'soap', None, None),
                        (2, u'lye', None, None),
                        (3, u'marla', u'marla', u'cancer'),
                    ], [
                        (1, u'IPv9', u'0578cc6.8db024'),
                        (2, u'git', u'Tyler Durden <tyler@mayhem.net>'),
                        (2, u'irc', u'durden')
                    ]))
            return self.db.pool.do(thd)
        d.addCallback(check_user)
        return d

    def test_addUser_race(self):
        def race_thd(conn):
            # note that this assumes that both inserts can happen "at once".
            # This is the case for DB engines that support transactions, but
            # not for MySQL.  so this test does not detect the potential MySQL
            # failure, which will generally result in a spurious failure.
            conn.execute(self.db.model.users.insert(),
                         uid=99, identifier='soap')
            conn.execute(self.db.model.users_info.insert(),
                         uid=99, attr_type='subspace_net_handle',
                         attr_data='Durden0924')
        d = self.db.users.findUserByAttr(identifier='soap',
                                         attr_type='subspace_net_handle',
                                         attr_data='Durden0924',
                                         _race_hook=race_thd)

        def check_user(uid):
            self.assertEqual(uid, 99)

            def thd(conn):
                users_tbl = self.db.model.users
                users_info_tbl = self.db.model.users_info
                users = conn.execute(users_tbl.select()).fetchall()
                infos = conn.execute(users_info_tbl.select()).fetchall()
                self.assertEqual(len(users), 1)
                self.assertEqual(users[0].uid, uid)
                self.assertEqual(users[0].identifier, 'soap')
                self.assertEqual(len(infos), 1)
                self.assertEqual(infos[0].uid, uid)
                self.assertEqual(infos[0].attr_type, 'subspace_net_handle')
                self.assertEqual(infos[0].attr_data, 'Durden0924')
            return self.db.pool.do(thd)
        d.addCallback(check_user)
        return d

    def test_addUser_existing_identifier(self):
        # see http://trac.buildbot.net/ticket/2587
        d = self.insertTestData(self.user1_rows)
        d.addCallback(lambda _: self.db.users.findUserByAttr(
            identifier='soap',  # same identifier
            attr_type='IPv9',
            attr_data='fffffff.ffffff'))  # different attr

        def check_user(uid):
            # creates a new user
            self.assertNotEqual(uid, 1)

            def thd(conn):
                users_tbl = self.db.model.users
                users_info_tbl = self.db.model.users_info
                users = conn.execute(
                    users_tbl.select(order_by=users_tbl.c.identifier)).fetchall()
                infos = conn.execute(
                    users_info_tbl.select(users_info_tbl.c.uid == uid)).fetchall()
                self.assertEqual(len(users), 2)
                self.assertEqual(users[1].uid, uid)
                self.assertEqual(users[1].identifier, 'soap_2')  # unique'd
                self.assertEqual(len(infos), 1)
                self.assertEqual(infos[0].attr_type, 'IPv9')
                self.assertEqual(infos[0].attr_data, 'fffffff.ffffff')
            return self.db.pool.do(thd)
        d.addCallback(check_user)
        return d

    def test_getUser(self):
        d = self.insertTestData(self.user1_rows)

        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)

        def check1(usdict):
            self.assertEqual(usdict, self.user1_dict)
        d.addCallback(check1)
        return d

    def test_getUser_bb(self):
        d = self.insertTestData(self.user3_rows)

        def get3(_):
            return self.db.users.getUser(3)
        d.addCallback(get3)

        def check3(usdict):
            self.assertEqual(usdict, self.user3_dict)
        d.addCallback(check3)
        return d

    def test_getUser_multi_attr(self):
        d = self.insertTestData(self.user2_rows)

        def get1(_):
            return self.db.users.getUser(2)
        d.addCallback(get1)

        def check1(usdict):
            self.assertEqual(usdict, self.user2_dict)
        d.addCallback(check1)
        return d

    def test_getUser_no_match(self):
        d = self.insertTestData(self.user1_rows)

        def get3(_):
            return self.db.users.getUser(3)
        d.addCallback(get3)

        def check3(none):
            self.assertEqual(none, None)
        d.addCallback(check3)
        return d

    def test_getUsers_none(self):
        d = self.db.users.getUsers()

        def check(res):
            self.assertEqual(res, [])
        d.addCallback(check)
        return d

    def test_getUsers(self):
        d = self.insertTestData(self.user1_rows)

        def get(_):
            return self.db.users.getUsers()
        d.addCallback(get)

        def check(res):
            self.assertEqual(res, [dict(uid=1, identifier='soap')])
        d.addCallback(check)
        return d

    def test_getUsers_multiple(self):
        d = self.insertTestData(self.user1_rows + self.user2_rows)

        def get(_):
            return self.db.users.getUsers()
        d.addCallback(get)

        def check(res):
            self.assertEqual(res, [dict(uid=1, identifier='soap'),
                                   dict(uid=2, identifier='lye')])
        d.addCallback(check)
        return d

    def test_getUserByUsername(self):
        d = self.insertTestData(self.user3_rows)

        def get3(_):
            return self.db.users.getUserByUsername("marla")
        d.addCallback(get3)

        def check3(res):
            self.assertEqual(res, self.user3_dict)
        d.addCallback(check3)
        return d

    def test_getUserByUsername_no_match(self):
        d = self.insertTestData(self.user3_rows)

        def get3(_):
            return self.db.users.getUserByUsername("tyler")
        d.addCallback(get3)

        def check3(none):
            self.assertEqual(none, None)
        d.addCallback(check3)
        return d

    def test_updateUser_existing_type(self):
        d = self.insertTestData(self.user1_rows)

        def update1(_):
            return self.db.users.updateUser(
                uid=1, attr_type='IPv9', attr_data='abcd.1234')
        d.addCallback(update1)

        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)

        def check1(usdict):
            self.assertEqual(usdict['IPv9'], 'abcd.1234')
            self.assertEqual(usdict['identifier'], 'soap')  # no change
        d.addCallback(check1)
        return d

    def test_updateUser_new_type(self):
        d = self.insertTestData(self.user1_rows)

        def update1(_):
            return self.db.users.updateUser(
                uid=1, attr_type='IPv4', attr_data='123.134.156.167')
        d.addCallback(update1)

        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)

        def check1(usdict):
            self.assertEqual(usdict['IPv4'], '123.134.156.167')
            self.assertEqual(usdict['IPv9'], '0578cc6.8db024')  # no change
            self.assertEqual(usdict['identifier'], 'soap')  # no change
        d.addCallback(check1)
        return d

    def test_updateUser_identifier(self):
        d = self.insertTestData(self.user1_rows)

        def update1(_):
            return self.db.users.updateUser(
                uid=1, identifier='lye')
        d.addCallback(update1)

        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)

        def check1(usdict):
            self.assertEqual(usdict['identifier'], 'lye')
            self.assertEqual(usdict['IPv9'], '0578cc6.8db024')  # no change
        d.addCallback(check1)
        return d

    def test_updateUser_bb(self):
        d = self.insertTestData(self.user3_rows)

        def update3(_):
            return self.db.users.updateUser(
                uid=3, bb_username='boss', bb_password='fired')
        d.addCallback(update3)

        def get3(_):
            return self.db.users.getUser(3)
        d.addCallback(get3)

        def check3(usdict):
            self.assertEqual(usdict['bb_username'], 'boss')
            self.assertEqual(usdict['bb_password'], 'fired')
            self.assertEqual(usdict['identifier'], 'marla')  # no change
        d.addCallback(check3)
        return d

    def test_updateUser_all(self):
        d = self.insertTestData(self.user1_rows)

        def update1(_):
            return self.db.users.updateUser(
                uid=1, identifier='lye', bb_username='marla',
                bb_password='cancer', attr_type='IPv4', attr_data='123.134.156.167')
        d.addCallback(update1)

        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)

        def check1(usdict):
            self.assertEqual(usdict['identifier'], 'lye')
            self.assertEqual(usdict['bb_username'], 'marla')
            self.assertEqual(usdict['bb_password'], 'cancer')
            self.assertEqual(usdict['IPv4'], '123.134.156.167')
            self.assertEqual(usdict['IPv9'], '0578cc6.8db024')  # no change
        d.addCallback(check1)
        return d

    def test_updateUser_race(self):
        # called from the db thread, this opens a *new* connection (to avoid
        # the existing transaction) and executes a conflicting insert in that
        # connection.  This will cause the insert in the db method to fail, and
        # the data in this insert (8.8.8.8) will appear below.
        transaction_wins = []
        if (self.db.pool.engine.dialect.name == 'sqlite' and
                self.db.pool.engine.url.database not in [None, ':memory:']):
            # It's not easy to work with file-based SQLite via multiple
            # connections, because SQLAlchemy (in it's default configuration)
            # locks file during working session.
            # TODO: This probably can be supported.
            raise unittest.SkipTest(
                "It's hard to test race condition with not in-memory SQLite")

        def race_thd(conn):
            conn = self.db.pool.engine.connect()
            try:
                r = conn.execute(self.db.model.users_info.insert(),
                                 uid=1, attr_type='IPv4',
                                 attr_data='8.8.8.8')
                r.close()
            except sqlalchemy.exc.OperationalError:
                # some engine (mysql innodb) will enforce lock until the transaction is over
                transaction_wins.append(True)
                # scope variable, we modify a list so that modification is visible in parent scope
        d = self.insertTestData(self.user1_rows)

        def update1(_):
            return self.db.users.updateUser(
                uid=1, attr_type='IPv4', attr_data='123.134.156.167',
                _race_hook=race_thd)
        d.addCallback(update1)

        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)

        def check1(usdict):
            self.assertEqual(usdict['identifier'], 'soap')
            if transaction_wins:
                self.assertEqual(usdict['IPv4'], '123.134.156.167')
            else:
                self.assertEqual(usdict['IPv4'], '8.8.8.8')
            self.assertEqual(usdict['IPv9'], '0578cc6.8db024')  # no change
        d.addCallback(check1)
        return d

    def test_update_NoMatch_identifier(self):
        d = self.insertTestData(self.user1_rows)

        def update3(_):
            return self.db.users.updateUser(
                uid=3, identifier='abcd')
        d.addCallback(update3)

        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)

        def check1(usdict):
            self.assertEqual(usdict['identifier'], 'soap')  # no change
        d.addCallback(check1)
        return d

    def test_update_NoMatch_attribute(self):
        d = self.insertTestData(self.user1_rows)

        def update3(_):
            return self.db.users.updateUser(
                uid=3, attr_type='abcd', attr_data='efgh')
        d.addCallback(update3)

        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)

        def check1(usdict):
            self.assertEqual(usdict['IPv9'], '0578cc6.8db024')  # no change
        d.addCallback(check1)
        return d

    def test_update_NoMatch_bb(self):
        d = self.insertTestData(self.user1_rows)

        def update3(_):
            return self.db.users.updateUser(
                uid=3, attr_type='marla', attr_data='cancer')
        d.addCallback(update3)

        def get1(_):
            return self.db.users.getUser(1)
        d.addCallback(get1)

        def check1(usdict):
            self.assertEqual(usdict['IPv9'], '0578cc6.8db024')  # no change
        d.addCallback(check1)
        return d

    def test_removeUser_uid(self):
        d = self.insertTestData(self.user1_rows)

        def remove1(_):
            return self.db.users.removeUser(1)
        d.addCallback(remove1)

        def check1(_):
            def thd(conn):
                r = conn.execute(self.db.model.users.select())
                r = r.fetchall()
                self.assertEqual(len(r), 0)
            return self.db.pool.do(thd)
        d.addCallback(check1)
        return d

    def test_removeNoMatch(self):
        d = self.insertTestData(self.user1_rows)

        def check(_):
            return self.db.users.removeUser(uid=3)
        d.addCallback(check)
        return d

    def test_identifierToUid_NoMatch(self):
        d = self.db.users.identifierToUid(identifier="soap")

        def check(res):
            self.assertEqual(res, None)
        d.addCallback(check)
        return d

    def test_identifierToUid_match(self):
        d = self.insertTestData(self.user1_rows)

        def ident2uid(_):
            return self.db.users.identifierToUid(identifier="soap")
        d.addCallback(ident2uid)

        def check(res):
            self.assertEqual(res, 1)
        d.addCallback(check)
        return d
