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

from twisted.trial import unittest

from buildbot.process.users import users
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster


class UsersTests(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self, wantDb=True)
        self.db = self.master.db
        self.test_sha = users.encrypt("cancer")

    def test_createUserObject_no_src(self):
        d = users.createUserObject(self.master, "Tyler Durden", None)

        def check(_):
            self.assertEqual(self.db.users.users, {})
            self.assertEqual(self.db.users.users_info, {})
        d.addCallback(check)
        return d

    def test_createUserObject_unrecognized_src(self):
        d = users.createUserObject(self.master, "Tyler Durden", 'blah')

        def check(_):
            self.assertEqual(self.db.users.users, {})
            self.assertEqual(self.db.users.users_info, {})
        d.addCallback(check)
        return d

    def test_createUserObject_git(self):
        d = users.createUserObject(self.master,
                                   "Tyler Durden <tyler@mayhem.net>", 'git')

        def check(_):
            self.assertEqual(self.db.users.users,
                             {1: dict(identifier='Tyler Durden <tyler@mayhem.net>',
                                      bb_username=None, bb_password=None)})
            self.assertEqual(self.db.users.users_info,
                             {1: [dict(attr_type="git",
                                       attr_data="Tyler Durden <tyler@mayhem.net>")]})
        d.addCallback(check)
        return d

    def test_createUserObject_svn(self):
        d = users.createUserObject(self.master, "tdurden", 'svn')

        def check(_):
            self.assertEqual(self.db.users.users,
                             {1: dict(identifier='tdurden',
                                      bb_username=None, bb_password=None)})
            self.assertEqual(self.db.users.users_info,
                             {1: [dict(attr_type="svn",
                                       attr_data="tdurden")]})
        d.addCallback(check)
        return d

    def test_createUserObject_hg(self):
        d = users.createUserObject(self.master,
                                   "Tyler Durden <tyler@mayhem.net>", 'hg')

        def check(_):
            self.assertEqual(self.db.users.users,
                             {1: dict(identifier='Tyler Durden <tyler@mayhem.net>',
                                      bb_username=None, bb_password=None)})
            self.assertEqual(self.db.users.users_info,
                             {1: [dict(attr_type="hg",
                                       attr_data="Tyler Durden <tyler@mayhem.net>")]})
        d.addCallback(check)
        return d

    def test_createUserObject_cvs(self):
        d = users.createUserObject(self.master, "tdurden", 'cvs')

        def check(_):
            self.assertEqual(self.db.users.users,
                             {1: dict(identifier='tdurden',
                                      bb_username=None, bb_password=None)})
            self.assertEqual(self.db.users.users_info,
                             {1: [dict(attr_type="cvs",
                                       attr_data="tdurden")]})
        d.addCallback(check)
        return d

    def test_createUserObject_darcs(self):
        d = users.createUserObject(self.master, "tyler@mayhem.net", 'darcs')

        def check(_):
            self.assertEqual(self.db.users.users,
                             {1: dict(identifier='tyler@mayhem.net',
                                      bb_username=None, bb_password=None)})
            self.assertEqual(self.db.users.users_info,
                             {1: [dict(attr_type="darcs",
                                       attr_data="tyler@mayhem.net")]})
        d.addCallback(check)
        return d

    def test_createUserObject_bzr(self):
        d = users.createUserObject(self.master, "Tyler Durden", 'bzr')

        def check(_):
            self.assertEqual(self.db.users.users,
                             {1: dict(identifier='Tyler Durden',
                                      bb_username=None, bb_password=None)})
            self.assertEqual(self.db.users.users_info,
                             {1: [dict(attr_type="bzr",
                                       attr_data="Tyler Durden")]})
        d.addCallback(check)
        return d

    def test_getUserContact_found(self):
        self.db.insertTestData([fakedb.User(uid=1, identifier='tdurden'),
                                fakedb.UserInfo(uid=1, attr_type='svn',
                                                attr_data='tdurden'),
                                fakedb.UserInfo(uid=1, attr_type='email',
                                                attr_data='tyler@mayhem.net')])
        d = users.getUserContact(self.master, contact_types=['email'], uid=1)

        def check(contact):
            self.assertEqual(contact, 'tyler@mayhem.net')
        d.addCallback(check)
        return d

    def test_getUserContact_key_not_found(self):
        self.db.insertTestData([fakedb.User(uid=1, identifier='tdurden'),
                                fakedb.UserInfo(uid=1, attr_type='svn',
                                                attr_data='tdurden'),
                                fakedb.UserInfo(uid=1, attr_type='email',
                                                attr_data='tyler@mayhem.net')])
        d = users.getUserContact(self.master, contact_types=['blargh'], uid=1)

        def check(contact):
            self.assertEqual(contact, None)
        d.addCallback(check)
        return d

    def test_getUserContact_uid_not_found(self):
        d = users.getUserContact(self.master, contact_types=['email'], uid=1)

        def check(contact):
            self.assertEqual(contact, None)
        d.addCallback(check)
        return d

    def test_check_passwd(self):
        res = users.check_passwd("cancer", self.test_sha)
        self.assertEqual(res, True)
