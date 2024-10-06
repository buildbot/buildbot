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

from buildbot.process.users import users
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin


class UsersTests(TestReactorMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self, wantDb=True)
        self.db = self.master.db
        self.test_sha = users.encrypt("cancer")

    async def test_createUserObject_no_src(self):
        await users.createUserObject(self.master, "Tyler Durden", None)

        self.assertEqual(self.db.users.users, {})
        self.assertEqual(self.db.users.users_info, {})

    async def test_createUserObject_unrecognized_src(self):
        await users.createUserObject(self.master, "Tyler Durden", 'blah')

        self.assertEqual(self.db.users.users, {})
        self.assertEqual(self.db.users.users_info, {})

    async def test_createUserObject_git(self):
        await users.createUserObject(self.master, "Tyler Durden <tyler@mayhem.net>", 'git')

        self.assertEqual(
            self.db.users.users,
            {
                1: {
                    "identifier": 'Tyler Durden <tyler@mayhem.net>',
                    "bb_username": None,
                    "bb_password": None,
                }
            },
        )
        self.assertEqual(
            self.db.users.users_info,
            {1: [{"attr_type": "git", "attr_data": "Tyler Durden <tyler@mayhem.net>"}]},
        )

    async def test_createUserObject_svn(self):
        await users.createUserObject(self.master, "tdurden", 'svn')

        self.assertEqual(
            self.db.users.users,
            {1: {"identifier": 'tdurden', "bb_username": None, "bb_password": None}},
        )
        self.assertEqual(
            self.db.users.users_info, {1: [{"attr_type": "svn", "attr_data": "tdurden"}]}
        )

    async def test_createUserObject_hg(self):
        await users.createUserObject(self.master, "Tyler Durden <tyler@mayhem.net>", 'hg')

        self.assertEqual(
            self.db.users.users,
            {
                1: {
                    "identifier": 'Tyler Durden <tyler@mayhem.net>',
                    "bb_username": None,
                    "bb_password": None,
                }
            },
        )
        self.assertEqual(
            self.db.users.users_info,
            {1: [{"attr_type": "hg", "attr_data": "Tyler Durden <tyler@mayhem.net>"}]},
        )

    async def test_createUserObject_cvs(self):
        await users.createUserObject(self.master, "tdurden", 'cvs')

        self.assertEqual(
            self.db.users.users,
            {1: {"identifier": 'tdurden', "bb_username": None, "bb_password": None}},
        )
        self.assertEqual(
            self.db.users.users_info, {1: [{"attr_type": "cvs", "attr_data": "tdurden"}]}
        )

    async def test_createUserObject_darcs(self):
        await users.createUserObject(self.master, "tyler@mayhem.net", 'darcs')

        self.assertEqual(
            self.db.users.users,
            {1: {"identifier": 'tyler@mayhem.net', "bb_username": None, "bb_password": None}},
        )
        self.assertEqual(
            self.db.users.users_info, {1: [{"attr_type": "darcs", "attr_data": "tyler@mayhem.net"}]}
        )

    async def test_createUserObject_bzr(self):
        await users.createUserObject(self.master, "Tyler Durden", 'bzr')

        self.assertEqual(
            self.db.users.users,
            {1: {"identifier": 'Tyler Durden', "bb_username": None, "bb_password": None}},
        )
        self.assertEqual(
            self.db.users.users_info, {1: [{"attr_type": 'bzr', "attr_data": 'Tyler Durden'}]}
        )

    async def test_getUserContact_found(self):
        self.db.insert_test_data([
            fakedb.User(uid=1, identifier='tdurden'),
            fakedb.UserInfo(uid=1, attr_type='svn', attr_data='tdurden'),
            fakedb.UserInfo(uid=1, attr_type='email', attr_data='tyler@mayhem.net'),
        ])
        contact = await users.getUserContact(self.master, contact_types=['email'], uid=1)

        self.assertEqual(contact, 'tyler@mayhem.net')

    async def test_getUserContact_key_not_found(self):
        self.db.insert_test_data([
            fakedb.User(uid=1, identifier='tdurden'),
            fakedb.UserInfo(uid=1, attr_type='svn', attr_data='tdurden'),
            fakedb.UserInfo(uid=1, attr_type='email', attr_data='tyler@mayhem.net'),
        ])
        contact = await users.getUserContact(self.master, contact_types=['blargh'], uid=1)

        self.assertEqual(contact, None)

    async def test_getUserContact_uid_not_found(self):
        contact = await users.getUserContact(self.master, contact_types=['email'], uid=1)

        self.assertEqual(contact, None)

    def test_check_passwd(self):
        res = users.check_passwd("cancer", self.test_sha)
        self.assertEqual(res, True)
