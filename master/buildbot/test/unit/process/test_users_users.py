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

import copy

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.db.users import UserModel
from buildbot.process.users import users
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin


class UsersTests(TestReactorMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.master = yield fakemaster.make_master(self, wantDb=True)
        self.test_sha = users.encrypt("cancer")

    @defer.inlineCallbacks
    def verify_users(self, users):
        users_no_attrs = copy.deepcopy(users)
        for user in users_no_attrs:
            user.attributes = None

        got_users = yield self.master.db.users.getUsers()
        self.assertEqual(got_users, users_no_attrs)

        for user in users:
            got_user = yield self.master.db.users.getUser(user.uid)
            self.assertEqual(got_user, user)

    @defer.inlineCallbacks
    def test_createUserObject_no_src(self):
        yield users.createUserObject(self.master, "Tyler Durden", None)
        got_users = yield self.master.db.users.getUsers()
        self.assertEqual(got_users, [])

    @defer.inlineCallbacks
    def test_createUserObject_unrecognized_src(self):
        yield users.createUserObject(self.master, "Tyler Durden", 'blah')
        got_users = yield self.master.db.users.getUsers()
        self.assertEqual(got_users, [])

    @defer.inlineCallbacks
    def test_createUserObject_git(self):
        yield users.createUserObject(self.master, "Tyler Durden <tyler@mayhem.net>", 'git')
        yield self.verify_users([
            UserModel(
                uid=1,
                identifier='Tyler Durden <tyler@mayhem.net>',
                bb_username=None,
                bb_password=None,
                attributes={'git': 'Tyler Durden <tyler@mayhem.net>'},
            )
        ])

    @defer.inlineCallbacks
    def test_createUserObject_svn(self):
        yield users.createUserObject(self.master, "tdurden", 'svn')

        yield self.verify_users([
            UserModel(
                uid=1,
                identifier='tdurden',
                bb_username=None,
                bb_password=None,
                attributes={'svn': 'tdurden'},
            )
        ])

    @defer.inlineCallbacks
    def test_createUserObject_hg(self):
        yield users.createUserObject(self.master, "Tyler Durden <tyler@mayhem.net>", 'hg')

        yield self.verify_users([
            UserModel(
                uid=1,
                identifier='Tyler Durden <tyler@mayhem.net>',
                bb_username=None,
                bb_password=None,
                attributes={'hg': 'Tyler Durden <tyler@mayhem.net>'},
            )
        ])

    @defer.inlineCallbacks
    def test_createUserObject_cvs(self):
        yield users.createUserObject(self.master, "tdurden", 'cvs')

        yield self.verify_users([
            UserModel(
                uid=1,
                identifier='tdurden',
                bb_username=None,
                bb_password=None,
                attributes={'cvs': 'tdurden'},
            )
        ])

    @defer.inlineCallbacks
    def test_createUserObject_darcs(self):
        yield users.createUserObject(self.master, "tyler@mayhem.net", 'darcs')

        yield self.verify_users([
            UserModel(
                uid=1,
                identifier='tyler@mayhem.net',
                bb_username=None,
                bb_password=None,
                attributes={'darcs': 'tyler@mayhem.net'},
            )
        ])

    @defer.inlineCallbacks
    def test_createUserObject_bzr(self):
        yield users.createUserObject(self.master, "Tyler Durden", 'bzr')

        yield self.verify_users([
            UserModel(
                uid=1,
                identifier='Tyler Durden',
                bb_username=None,
                bb_password=None,
                attributes={'bzr': 'Tyler Durden'},
            )
        ])

    @defer.inlineCallbacks
    def test_getUserContact_found(self):
        yield self.master.db.insert_test_data([
            fakedb.User(uid=1, identifier='tdurden'),
            fakedb.UserInfo(uid=1, attr_type='svn', attr_data='tdurden'),
            fakedb.UserInfo(uid=1, attr_type='email', attr_data='tyler@mayhem.net'),
        ])
        contact = yield users.getUserContact(self.master, contact_types=['email'], uid=1)

        self.assertEqual(contact, 'tyler@mayhem.net')

    @defer.inlineCallbacks
    def test_getUserContact_key_not_found(self):
        yield self.master.db.insert_test_data([
            fakedb.User(uid=1, identifier='tdurden'),
            fakedb.UserInfo(uid=1, attr_type='svn', attr_data='tdurden'),
            fakedb.UserInfo(uid=1, attr_type='email', attr_data='tyler@mayhem.net'),
        ])
        contact = yield users.getUserContact(self.master, contact_types=['blargh'], uid=1)

        self.assertEqual(contact, None)

    @defer.inlineCallbacks
    def test_getUserContact_uid_not_found(self):
        contact = yield users.getUserContact(self.master, contact_types=['email'], uid=1)

        self.assertEqual(contact, None)

    def test_check_passwd(self):
        res = users.check_passwd("cancer", self.test_sha)
        self.assertEqual(res, True)
