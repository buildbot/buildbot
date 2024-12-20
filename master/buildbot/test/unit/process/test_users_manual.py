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

# this class is known to contain cruft and will be looked at later, so
# no current implementation utilizes it aside from scripts.runner.

from unittest import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.db.users import UserModel
from buildbot.process.users import manual
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin


class ManualUsersMixin:
    """
    This class fakes out the master/db components to test the manual
    user managers located in process.users.manual.
    """

    @defer.inlineCallbacks
    def setUpManualUsers(self):
        self.master = yield fakemaster.make_master(self, wantDb=True)


class TestUsersBase(unittest.TestCase):
    """
    Not really sure what there is to test, aside from _setUpManualUsers getting
    self.master set.
    """


class TestCommandlineUserManagerPerspective(TestReactorMixin, unittest.TestCase, ManualUsersMixin):
    def setUp(self):
        self.setup_test_reactor()
        self.setUpManualUsers()

    def call_perspective_commandline(self, *args):
        persp = manual.CommandlineUserManagerPerspective(self.master)
        return persp.perspective_commandline(*args)

    @defer.inlineCallbacks
    def test_perspective_commandline_add(self):
        yield self.call_perspective_commandline(
            'add', None, None, None, [{'identifier': 'x', 'git': 'x'}]
        )

        usdict = yield self.master.db.users.getUser(1)

        self.assertEqual(
            usdict,
            UserModel(
                uid=1, identifier='x', bb_username=None, bb_password=None, attributes={"git": 'x'}
            ),
        )

    @defer.inlineCallbacks
    def test_perspective_commandline_update(self):
        yield self.call_perspective_commandline(
            'add', None, None, None, [{'identifier': 'x', 'svn': 'x'}]
        )
        yield self.call_perspective_commandline(
            'update', None, None, None, [{'identifier': 'x', 'svn': 'y'}]
        )

        usdict = yield self.master.db.users.getUser(1)

        self.assertEqual(
            usdict,
            UserModel(
                uid=1, identifier='x', bb_username=None, bb_password=None, attributes={"svn": 'y'}
            ),
        )

    @defer.inlineCallbacks
    def test_perspective_commandline_update_bb(self):
        yield self.call_perspective_commandline(
            'add', None, None, None, [{'identifier': 'x', 'svn': 'x'}]
        )
        yield self.call_perspective_commandline(
            'update', 'bb_user', 'hashed_bb_pass', None, [{'identifier': 'x'}]
        )

        usdict = yield self.master.db.users.getUser(1)

        self.assertEqual(
            usdict,
            UserModel(
                uid=1,
                identifier='x',
                bb_username='bb_user',
                bb_password='hashed_bb_pass',
                attributes={"svn": 'x'},
            ),
        )

    @defer.inlineCallbacks
    def test_perspective_commandline_update_both(self):
        yield self.call_perspective_commandline(
            'add', None, None, None, [{'identifier': 'x', 'svn': 'x'}]
        )
        yield self.call_perspective_commandline(
            'update', 'bb_user', 'hashed_bb_pass', None, [{'identifier': 'x', 'svn': 'y'}]
        )

        usdict = yield self.master.db.users.getUser(1)
        self.assertEqual(
            usdict,
            UserModel(
                uid=1,
                identifier='x',
                bb_username='bb_user',
                bb_password='hashed_bb_pass',
                attributes={"svn": 'y'},
            ),
        )

    @defer.inlineCallbacks
    def test_perspective_commandline_remove(self):
        yield self.call_perspective_commandline(
            'add', None, None, None, [{'identifier': 'h@c', 'git': 'hi <h@c>'}]
        )
        yield self.call_perspective_commandline('remove', None, None, ['h@c'], None)
        res = yield self.master.db.users.getUser(1)
        self.assertEqual(res, None)

    @defer.inlineCallbacks
    def test_perspective_commandline_get(self):
        yield self.call_perspective_commandline(
            'add', None, None, None, [{'identifier': 'x', 'svn': 'x'}]
        )

        yield self.call_perspective_commandline('get', None, None, ['x'], None)

        res = yield self.master.db.users.getUser(1)
        self.assertEqual(
            res,
            UserModel(
                uid=1,
                identifier='x',
                bb_username=None,
                bb_password=None,
                attributes={"svn": 'x'},
            ),
        )

    @defer.inlineCallbacks
    def test_perspective_commandline_get_multiple_attrs(self):
        yield self.call_perspective_commandline(
            'add', None, None, None, [{'identifier': 'x', 'svn': 'x', 'git': 'x@c'}]
        )
        yield self.call_perspective_commandline('get', None, None, ['x'], None)

        res = yield self.master.db.users.getUser(1)
        self.assertEqual(
            res,
            UserModel(
                uid=1,
                identifier='x',
                bb_username=None,
                bb_password=None,
                attributes={"svn": 'x', 'git': 'x@c'},
            ),
        )

    @defer.inlineCallbacks
    def test_perspective_commandline_add_format(self):
        result = yield self.call_perspective_commandline(
            'add', None, None, None, [{'identifier': 'x', 'svn': 'x'}]
        )

        exp_format = "user(s) added:\nidentifier: x\nuid: 1\n\n"
        self.assertEqual(result, exp_format)

    @defer.inlineCallbacks
    def test_perspective_commandline_update_format(self):
        yield self.call_perspective_commandline(
            'add', None, None, None, [{'identifier': 'x', 'svn': 'x'}]
        )
        result = yield self.call_perspective_commandline(
            'update', None, None, None, [{'identifier': 'x', 'svn': 'y'}]
        )

        exp_format = 'user(s) updated:\nidentifier: x\n'
        self.assertEqual(result, exp_format)

    @defer.inlineCallbacks
    def test_perspective_commandline_remove_format(self):
        yield self.call_perspective_commandline(
            'add', None, None, None, [{'identifier': 'h@c', 'git': 'hi <h@c>'}]
        )
        result = yield self.call_perspective_commandline('remove', None, None, ['h@c'], None)

        exp_format = "user(s) removed:\nidentifier: h@c\n"
        self.assertEqual(result, exp_format)

    @defer.inlineCallbacks
    def test_perspective_commandline_get_format(self):
        yield self.call_perspective_commandline(
            'add', None, None, None, [{'identifier': 'x@y', 'git': 'x <x@y>'}]
        )

        result = yield self.call_perspective_commandline('get', None, None, ['x@y'], None)

        exp_format = (
            'user(s) found:\n'
            'uid: 1\n'
            'identifier: x@y\n'
            'bb_username: None\n'
            'attributes:\n'
            '\tgit: x <x@y>\n'
            '\n'
        )
        self.assertEqual(result, exp_format)

    @defer.inlineCallbacks
    def test_perspective_commandline_remove_no_match_format(self):
        result = yield self.call_perspective_commandline('remove', None, None, ['x'], None)

        exp_format = "user(s) removed:\n"
        self.assertEqual(result, exp_format)

    @defer.inlineCallbacks
    def test_perspective_commandline_get_no_match_format(self):
        result = yield self.call_perspective_commandline('get', None, None, ['x'], None)

        exp_format = "user(s) found:\nno match found\n"
        self.assertEqual(result, exp_format)


class TestCommandlineUserManager(TestReactorMixin, unittest.TestCase, ManualUsersMixin):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.setUpManualUsers()
        self.manual_component = manual.CommandlineUserManager(
            username="user", passwd="userpw", port="9990"
        )
        yield self.manual_component.setServiceParent(self.master)

    @defer.inlineCallbacks
    def test_no_userpass(self):
        with self.assertRaises(AssertionError):
            yield defer.maybeDeferred(manual.CommandlineUserManager)

    @defer.inlineCallbacks
    def test_no_port(self):
        with self.assertRaises(AssertionError):
            yield manual.CommandlineUserManager(username="x", passwd="y")

    @defer.inlineCallbacks
    def test_service(self):
        # patch out the pbmanager's 'register' command both to be sure
        # the registration is correct and to get a copy of the factory
        registration = mock.Mock()
        registration.unregister = lambda: defer.succeed(None)
        self.master.pbmanager = mock.Mock()

        def register(portstr, user, passwd, factory):
            self.assertEqual([portstr, user, passwd], ['9990', 'user', 'userpw'])
            self.got_factory = factory
            return defer.succeed(registration)

        self.master.pbmanager.register = register

        yield self.manual_component.startService()

        persp = self.got_factory(mock.Mock(), 'user')
        self.assertTrue(isinstance(persp, manual.CommandlineUserManagerPerspective))

        yield self.manual_component.stopService()
