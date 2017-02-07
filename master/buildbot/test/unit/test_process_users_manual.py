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

from __future__ import absolute_import
from __future__ import print_function

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.users import manual
from buildbot.test.fake import fakemaster


class ManualUsersMixin(object):

    """
    This class fakes out the master/db components to test the manual
    user managers located in process.users.manual.
    """

    def setUpManualUsers(self):
        self.master = fakemaster.make_master(testcase=self, wantDb=True)


class TestUsersBase(unittest.TestCase):

    """
    Not really sure what there is to test, aside from _setUpManualUsers getting
    self.master set.
    """
    pass


class TestCommandlineUserManagerPerspective(unittest.TestCase, ManualUsersMixin):

    def setUp(self):
        self.setUpManualUsers()

    def call_perspective_commandline(self, *args):
        persp = manual.CommandlineUserManagerPerspective(self.master)
        return persp.perspective_commandline(*args)

    def test_perspective_commandline_add(self):
        d = self.call_perspective_commandline('add', None, None, None,
                                              [{'identifier': 'x', 'git': 'x'}])

        def check_get(_):
            d = self.master.db.users.getUser(1)

            def real_check(usdict):
                self.assertEqual(usdict, dict(uid=1,
                                              identifier='x',
                                              bb_username=None,
                                              bb_password=None,
                                              git='x'))
            d.addCallback(real_check)
            return d
        d.addCallback(check_get)
        return d

    def test_perspective_commandline_update(self):
        d = self.call_perspective_commandline('add', None, None, None,
                                              [{'identifier': 'x', 'svn': 'x'}])
        d.addCallback(lambda _:
                      self.call_perspective_commandline(
                          'update', None, None, None,
                          [{'identifier': 'x', 'svn': 'y'}]))

        def check(_):
            d = self.master.db.users.getUser(1)

            def real_check(usdict):
                self.assertEqual(usdict, dict(uid=1,
                                              identifier='x',
                                              bb_username=None,
                                              bb_password=None,
                                              svn='y'))
            d.addCallback(real_check)
            return d
        d.addCallback(check)
        return d

    def test_perspective_commandline_update_bb(self):
        d = self.call_perspective_commandline('add', None, None, None,
                                              [{'identifier': 'x',
                                                'svn': 'x'}])
        d.addCallback(lambda _:
                      self.call_perspective_commandline(
                          'update', 'bb_user',
                          'hashed_bb_pass', None,
                          [{'identifier': 'x'}]))

        def check(_):
            d = self.master.db.users.getUser(1)

            def real_check(usdict):
                self.assertEqual(usdict, dict(uid=1,
                                              identifier='x',
                                              bb_username='bb_user',
                                              bb_password='hashed_bb_pass',
                                              svn='x'))
            d.addCallback(real_check)
            return d
        d.addCallback(check)
        return d

    def test_perspective_commandline_update_both(self):
        d = self.call_perspective_commandline('add', None, None, None,
                                              [{'identifier': 'x',
                                                'svn': 'x'}])
        d.addCallback(lambda _:
                      self.call_perspective_commandline(
                          'update', 'bb_user',
                          'hashed_bb_pass', None,
                          [{'identifier': 'x',
                            'svn': 'y'}]))

        def check(_):
            d = self.master.db.users.getUser(1)

            def real_check(usdict):
                self.assertEqual(usdict, dict(uid=1,
                                              identifier='x',
                                              bb_username='bb_user',
                                              bb_password='hashed_bb_pass',
                                              svn='y'))
            d.addCallback(real_check)
            return d
        d.addCallback(check)
        return d

    def test_perspective_commandline_remove(self):
        d = self.call_perspective_commandline('add', None, None, None,
                                              [{'identifier': 'h@c',
                                                'git': 'hi <h@c>'}])
        d.addCallback(lambda _:
                      self.call_perspective_commandline('remove', None,
                                                        None, ['x'], None))

        def check(_):
            d = self.master.db.users.getUser('x')

            def real_check(res):
                self.assertEqual(res, None)
            d.addCallback(real_check)
            return d
        d.addCallback(check)
        return d

    def test_perspective_commandline_get(self):
        d = self.call_perspective_commandline('add', None, None, None,
                                              [{'identifier': 'x',
                                                'svn': 'x'}])
        d.addCallback(lambda _:
                      self.call_perspective_commandline('get', None, None,
                                                        ['x'], None))

        def check(_):
            d = self.master.db.users.getUser(1)

            def real_check(res):
                self.assertEqual(res, dict(uid=1,
                                           identifier='x',
                                           bb_username=None,
                                           bb_password=None,
                                           svn='x'))
            d.addCallback(real_check)
            return d
        d.addCallback(check)
        return d

    def test_perspective_commandline_get_multiple_attrs(self):
        d = self.call_perspective_commandline('add', None, None, None,
                                              [{'identifier': 'x',
                                                'svn': 'x',
                                                'git': 'x@c'}])
        d.addCallback(lambda _:
                      self.call_perspective_commandline('get', None, None,
                                                        ['x'], None))

        def check(_):
            d = self.master.db.users.getUser(1)

            def real_check(res):
                self.assertEqual(res, dict(uid=1,
                                           identifier='x',
                                           bb_username=None,
                                           bb_password=None,
                                           svn='x',
                                           git='x@c'))
            d.addCallback(real_check)
            return d
        d.addCallback(check)
        return d

    def test_perspective_commandline_add_format(self):
        d = self.call_perspective_commandline('add', None, None, None,
                                              [{'identifier': 'x', 'svn': 'x'}])

        def check(result):
            exp_format = "user(s) added:\nidentifier: x\nuid: 1\n\n"
            self.assertEqual(result, exp_format)
        d.addCallback(check)
        return d

    def test_perspective_commandline_update_format(self):
        d = self.call_perspective_commandline('add', None, None, None,
                                              [{'identifier': 'x', 'svn': 'x'}])
        d.addCallback(lambda _:
                      self.call_perspective_commandline('update', None, None, None,
                                                        [{'identifier': 'x',
                                                          'svn': 'y'}]))

        def check(result):
            exp_format = 'user(s) updated:\nidentifier: x\n'
            self.assertEqual(result, exp_format)
        d.addCallback(check)
        return d

    def test_perspective_commandline_remove_format(self):
        d = self.call_perspective_commandline('add', None, None, None,
                                              [{'identifier': 'h@c',
                                                'git': 'hi <h@c>'}])
        d.addCallback(lambda _: self.call_perspective_commandline('remove',
                                                                  None, None,
                                                                  ['h@c'],
                                                                  None))

        def check(result):
            exp_format = "user(s) removed:\nidentifier: h@c\n"
            self.assertEqual(result, exp_format)
        d.addCallback(check)
        return d

    def test_perspective_commandline_get_format(self):
        d = self.call_perspective_commandline('add', None, None, None,
                                              [{'identifier': 'x@y', 'git': 'x <x@y>'}])
        d.addCallback(lambda _:
                      self.call_perspective_commandline('get', None, None,
                                                        ['x@y'], None))

        def check(result):
            exp_format = ('user(s) found:\nbb_username: None\n'
                         'git: x <x@y>\nidentifier: x@y\n'
                         'uid: 1\n\n')
            self.assertEqual(result, exp_format)
        d.addCallback(check)
        return d

    def test_perspective_commandline_remove_no_match_format(self):
        d = self.call_perspective_commandline(
            'remove', None, None, ['x'], None)

        def check(result):
            exp_format = "user(s) removed:\n"
            self.assertEqual(result, exp_format)
        d.addCallback(check)
        return d

    def test_perspective_commandline_get_no_match_format(self):
        d = self.call_perspective_commandline('get', None, None, ['x'], None)

        def check(result):
            exp_format = "user(s) found:\nno match found\n"
            self.assertEqual(result, exp_format)
        d.addCallback(check)
        return d


class TestCommandlineUserManager(unittest.TestCase, ManualUsersMixin):

    def setUp(self):
        self.setUpManualUsers()
        self.manual_component = manual.CommandlineUserManager(username="user",
                                                              passwd="userpw",
                                                              port="9990")
        self.manual_component.setServiceParent(self.master)

    def test_no_userpass(self):
        d = defer.maybeDeferred(lambda: manual.CommandlineUserManager())
        return self.assertFailure(d, AssertionError)

    def test_no_port(self):
        d = defer.maybeDeferred(lambda: manual.CommandlineUserManager(username="x",
                                                                      passwd="y"))
        return self.assertFailure(d, AssertionError)

    def test_service(self):
        # patch out the pbmanager's 'register' command both to be sure
        # the registration is correct and to get a copy of the factory
        registration = mock.Mock()
        registration.unregister = lambda: defer.succeed(None)
        self.master.pbmanager = mock.Mock()

        def register(portstr, user, passwd, factory):
            self.assertEqual([portstr, user, passwd],
                             ['9990', 'user', 'userpw'])
            self.got_factory = factory
            return registration
        self.master.pbmanager.register = register

        self.manual_component.startService()

        persp = self.got_factory(mock.Mock(), 'user')
        self.assertTrue(
            isinstance(persp, manual.CommandlineUserManagerPerspective))

        return self.manual_component.stopService()
