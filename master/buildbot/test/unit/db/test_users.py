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

import sqlalchemy
from twisted.trial import unittest

from buildbot.db import users
from buildbot.test import fakedb
from buildbot.test.util import connector_component


class TestUsersConnectorComponent(connector_component.ConnectorComponentMixin, unittest.TestCase):
    async def setUp(self):
        await self.setUpConnectorComponent(
            table_names=[
                'users',
                'users_info',
                'changes',
                'change_users',
                'sourcestamps',
                'patches',
            ]
        )

        self.db.users = users.UsersConnectorComponent(self.db)

    def tearDown(self):
        return self.tearDownConnectorComponent()

    # sample user data

    user1_rows = [
        fakedb.User(uid=1, identifier='soap'),
        fakedb.UserInfo(uid=1, attr_type='IPv9', attr_data='0578cc6.8db024'),
    ]

    user2_rows = [
        fakedb.User(uid=2, identifier='lye'),
        fakedb.UserInfo(uid=2, attr_type='git', attr_data='Tyler Durden <tyler@mayhem.net>'),
        fakedb.UserInfo(uid=2, attr_type='irc', attr_data='durden'),
    ]

    user3_rows = [fakedb.User(uid=3, identifier='marla', bb_username='marla', bb_password='cancer')]

    user1_model = users.UserModel(
        uid=1,
        identifier='soap',
        bb_username=None,
        bb_password=None,
        attributes={
            'IPv9': '0578cc6.8db024',
        },
    )

    user2_model = users.UserModel(
        uid=2,
        identifier='lye',
        bb_username=None,
        bb_password=None,
        attributes={
            'irc': 'durden',
            'git': 'Tyler Durden <tyler@mayhem.net>',
        },
    )

    user3_model = users.UserModel(
        uid=3,
        identifier='marla',
        bb_username='marla',
        bb_password='cancer',
        attributes={},
    )

    # tests

    async def test_addUser_new(self):
        uid = await self.db.users.findUserByAttr(
            identifier='soap', attr_type='subspace_net_handle', attr_data='Durden0924'
        )

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

        await self.db.pool.do(thd)

    async def test_addUser_existing(self):
        await self.insert_test_data(self.user1_rows)
        uid = await self.db.users.findUserByAttr(
            identifier='soapy', attr_type='IPv9', attr_data='0578cc6.8db024'
        )

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

        await self.db.pool.do(thd)

    async def test_findUser_existing(self):
        await self.insert_test_data(self.user1_rows + self.user2_rows + self.user3_rows)
        uid = await self.db.users.findUserByAttr(
            identifier='lye', attr_type='git', attr_data='Tyler Durden <tyler@mayhem.net>'
        )

        self.assertEqual(uid, 2)

        def thd(conn):
            users_tbl = self.db.model.users
            users_info_tbl = self.db.model.users_info
            users = conn.execute(users_tbl.select()).fetchall()
            infos = conn.execute(users_info_tbl.select()).fetchall()
            self.assertEqual(
                (sorted([tuple(u) for u in users]), sorted([tuple(i) for i in infos])),
                (
                    [
                        (1, 'soap', None, None),
                        (2, 'lye', None, None),
                        (3, 'marla', 'marla', 'cancer'),
                    ],
                    [
                        (1, 'IPv9', '0578cc6.8db024'),
                        (2, 'git', 'Tyler Durden <tyler@mayhem.net>'),
                        (2, 'irc', 'durden'),
                    ],
                ),
            )

        await self.db.pool.do(thd)

    async def test_addUser_race(self):
        def race_thd(conn):
            # note that this assumes that both inserts can happen "at once".
            # This is the case for DB engines that support transactions, but
            # not for MySQL.  so this test does not detect the potential MySQL
            # failure, which will generally result in a spurious failure.
            conn.execute(self.db.model.users.insert().values(uid=99, identifier='soap'))
            conn.execute(
                self.db.model.users_info.insert().values(
                    uid=99,
                    attr_type='subspace_net_handle',
                    attr_data='Durden0924',
                )
            )
            conn.commit()

        uid = await self.db.users.findUserByAttr(
            identifier='soap',
            attr_type='subspace_net_handle',
            attr_data='Durden0924',
            _race_hook=race_thd,
        )

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

        await self.db.pool.do(thd)

    async def test_addUser_existing_identifier(self):
        # see http://trac.buildbot.net/ticket/2587
        await self.insert_test_data(self.user1_rows)
        uid = await self.db.users.findUserByAttr(
            identifier='soap',  # same identifier
            attr_type='IPv9',
            attr_data='fffffff.ffffff',
        )  # different attr

        # creates a new user
        self.assertNotEqual(uid, 1)

        def thd(conn):
            users_tbl = self.db.model.users
            users_info_tbl = self.db.model.users_info
            users = conn.execute(users_tbl.select().order_by(users_tbl.c.identifier)).fetchall()
            infos = conn.execute(
                users_info_tbl.select().where(users_info_tbl.c.uid == uid)
            ).fetchall()
            self.assertEqual(len(users), 2)
            self.assertEqual(users[1].uid, uid)
            self.assertEqual(users[1].identifier, 'soap_2')  # unique'd
            self.assertEqual(len(infos), 1)
            self.assertEqual(infos[0].attr_type, 'IPv9')
            self.assertEqual(infos[0].attr_data, 'fffffff.ffffff')

        await self.db.pool.do(thd)

    async def test_getUser(self):
        await self.insert_test_data(self.user1_rows)

        usdict = await self.db.users.getUser(1)

        self.assertEqual(usdict, self.user1_model)

    async def test_getUser_bb(self):
        await self.insert_test_data(self.user3_rows)

        usdict = await self.db.users.getUser(3)

        self.assertEqual(usdict, self.user3_model)

    async def test_getUser_multi_attr(self):
        await self.insert_test_data(self.user2_rows)

        usdict = await self.db.users.getUser(2)

        self.assertEqual(usdict, self.user2_model)

    async def test_getUser_no_match(self):
        await self.insert_test_data(self.user1_rows)

        none = await self.db.users.getUser(3)

        self.assertEqual(none, None)

    async def test_getUsers_none(self):
        res = await self.db.users.getUsers()

        self.assertEqual(res, [])

    async def test_getUsers(self):
        await self.insert_test_data(self.user1_rows)

        res = await self.db.users.getUsers()

        self.assertEqual(res, [users.UserModel(uid=1, identifier='soap')])

    async def test_getUsers_multiple(self):
        await self.insert_test_data(self.user1_rows + self.user2_rows)

        res = await self.db.users.getUsers()

        self.assertEqual(
            res,
            [users.UserModel(uid=1, identifier='soap'), users.UserModel(uid=2, identifier='lye')],
        )

    async def test_getUserByUsername(self):
        await self.insert_test_data(self.user3_rows)

        res = await self.db.users.getUserByUsername("marla")

        self.assertEqual(res, self.user3_model)

    async def test_getUserByUsername_no_match(self):
        await self.insert_test_data(self.user3_rows)

        none = await self.db.users.getUserByUsername("tyler")

        self.assertEqual(none, None)

    async def test_updateUser_existing_type(self):
        await self.insert_test_data(self.user1_rows)

        await self.db.users.updateUser(uid=1, attr_type='IPv9', attr_data='abcd.1234')

        usdict = await self.db.users.getUser(1)

        self.assertEqual(usdict.attributes['IPv9'], 'abcd.1234')
        self.assertEqual(usdict.identifier, 'soap')  # no change

    async def test_updateUser_new_type(self):
        await self.insert_test_data(self.user1_rows)

        await self.db.users.updateUser(uid=1, attr_type='IPv4', attr_data='123.134.156.167')

        usdict = await self.db.users.getUser(1)

        self.assertEqual(usdict.attributes['IPv4'], '123.134.156.167')
        self.assertEqual(usdict.attributes['IPv9'], '0578cc6.8db024')  # no change
        self.assertEqual(usdict.identifier, 'soap')  # no change

    async def test_updateUser_identifier(self):
        await self.insert_test_data(self.user1_rows)

        await self.db.users.updateUser(uid=1, identifier='lye')

        usdict = await self.db.users.getUser(1)

        self.assertEqual(usdict.identifier, 'lye')
        self.assertEqual(usdict.attributes['IPv9'], '0578cc6.8db024')  # no change

    async def test_updateUser_bb(self):
        await self.insert_test_data(self.user3_rows)

        await self.db.users.updateUser(uid=3, bb_username='boss', bb_password='fired')

        usdict = await self.db.users.getUser(3)

        self.assertEqual(usdict.bb_username, 'boss')
        self.assertEqual(usdict.bb_password, 'fired')
        self.assertEqual(usdict.identifier, 'marla')  # no change

    async def test_updateUser_all(self):
        await self.insert_test_data(self.user1_rows)

        await self.db.users.updateUser(
            uid=1,
            identifier='lye',
            bb_username='marla',
            bb_password='cancer',
            attr_type='IPv4',
            attr_data='123.134.156.167',
        )

        usdict = await self.db.users.getUser(1)

        self.assertEqual(
            usdict,
            users.UserModel(
                uid=1,
                identifier='lye',
                bb_username='marla',
                bb_password='cancer',
                attributes={
                    'IPv4': '123.134.156.167',
                    'IPv9': '0578cc6.8db024',  # no change
                },
            ),
        )

    async def test_updateUser_race(self):
        # called from the db thread, this opens a *new* connection (to avoid
        # the existing transaction) and executes a conflicting insert in that
        # connection.  This will cause the insert in the db method to fail, and
        # the data in this insert (8.8.8.8) will appear below.
        race_condition_committed = []
        if (
            self.db.pool.engine.dialect.name == 'sqlite'
            and self.db.pool.engine.url.database not in [None, ':memory:']
        ):
            # It's not easy to work with file-based SQLite via multiple
            # connections, because SQLAlchemy (in it's default configuration)
            # locks file during working session.
            # TODO: This probably can be supported.
            raise unittest.SkipTest("It's hard to test race condition with not in-memory SQLite")

        def race_thd(conn):
            conn = self.db.pool.engine.connect()
            try:
                r = conn.execute(
                    self.db.model.users_info.insert().values(
                        uid=1, attr_type='IPv4', attr_data='8.8.8.8'
                    )
                )
                conn.commit()
                r.close()
                conn.close()
                race_condition_committed.append(True)
            except (sqlalchemy.exc.IntegrityError, sqlalchemy.exc.ProgrammingError):
                # some engine (mysql innodb) will enforce lock until the transaction is over
                race_condition_committed.append(False)
                # scope variable, we modify a list so that modification is visible in parent scope

        await self.insert_test_data(self.user1_rows)

        await self.db.users.updateUser(
            uid=1, attr_type='IPv4', attr_data='123.134.156.167', _race_hook=race_thd
        )

        if not race_condition_committed:
            raise RuntimeError('programmer error: race condition was not called')

        usdict = await self.db.users.getUser(1)

        self.assertEqual(usdict.identifier, 'soap')
        if race_condition_committed[0] == self.db.has_native_upsert:
            self.assertEqual(usdict.attributes['IPv4'], '123.134.156.167')
        else:
            self.assertEqual(usdict.attributes['IPv4'], '8.8.8.8')
        self.assertEqual(usdict.attributes['IPv9'], '0578cc6.8db024')  # no change

    async def test_update_NoMatch_identifier(self):
        await self.insert_test_data(self.user1_rows)

        await self.db.users.updateUser(uid=3, identifier='abcd')

        usdict = await self.db.users.getUser(1)

        self.assertEqual(usdict.identifier, 'soap')  # no change

    async def test_update_NoMatch_attribute(self):
        await self.insert_test_data(self.user1_rows)

        await self.db.users.updateUser(uid=3, attr_type='abcd', attr_data='efgh')

        usdict = await self.db.users.getUser(1)

        self.assertEqual(usdict.attributes['IPv9'], '0578cc6.8db024')  # no change

    async def test_update_NoMatch_bb(self):
        await self.insert_test_data(self.user1_rows)

        await self.db.users.updateUser(uid=3, attr_type='marla', attr_data='cancer')

        usdict = await self.db.users.getUser(1)

        self.assertEqual(usdict.attributes['IPv9'], '0578cc6.8db024')  # no change

    async def test_removeUser_uid(self):
        await self.insert_test_data(self.user1_rows)

        await self.db.users.removeUser(1)

        def thd(conn):
            r = conn.execute(self.db.model.users.select())
            r = r.fetchall()
            self.assertEqual(len(r), 0)

        await self.db.pool.do(thd)

    async def test_removeNoMatch(self):
        await self.insert_test_data(self.user1_rows)

        await self.db.users.removeUser(uid=3)

    async def test_identifierToUid_NoMatch(self):
        res = await self.db.users.identifierToUid(identifier="soap")

        self.assertEqual(res, None)

    async def test_identifierToUid_match(self):
        await self.insert_test_data(self.user1_rows)

        res = await self.db.users.identifierToUid(identifier="soap")

        self.assertEqual(res, 1)
