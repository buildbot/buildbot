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

import mock
from twisted.trial import unittest
from twisted.internet import defer

from buildbot.process.users import manual
from buildbot.test.util import users

class TestUsersBase(unittest.TestCase):
    """
    Not really sure what there is to test, aside from _setUpManualUsers getting
    self.master set.
    """
    pass

class TestCommandline_Users_Perspective(unittest.TestCase, users.ManualUsersMixin):

    def setUp(self):
        self.setUpManualUsers()
        self.clusers = self.attachManualUsers(manual.Commandline_Users())

    def tearDown(self):
        self.tearDownManualUsers()

    def call_perspective_commandline(self, *args):
        persp = manual.Commandline_Users_Perspective(self.clusers.master)
        return persp.perspective_commandline(*args)

    def test_perspective_commandline_add(self):
        d = self.call_perspective_commandline('add', None, [{'identifier':'x',
                                                             'a':'b'}])
        def check(_):
            d = self.clusers.master.db.users.getUser('x')
            def real_check(usdict):
                self.assertEqual(usdict, dict(identifier='x', a='b', uid=1))
            d.addCallback(real_check)
            return d
        d.addCallback(check)
        return d

    def test_perspective_commandline_update(self):
        d = self.call_perspective_commandline('add', None,
                                              [{'identifier':'x', 'a':'b'}])
        d.addCallback(lambda _ :
                          self.call_perspective_commandline('update', None,
                                             [{'identifier':'x', 'a':'c'}]))
        def check(_):
            d = self.clusers.master.db.users.getUser('x')
            def real_check(usdict):
                self.assertEqual(usdict, dict(identifier='x', a='c', uid=1))
            d.addCallback(real_check)
            return d
        d.addCallback(check)
        return d

    def test_perspective_commandline_remove(self):
        d = self.call_perspective_commandline('add', None,
                                              [{'identifier':'x', 'a':'c'}])
        d.addCallback(lambda _ :
                          self.call_perspective_commandline('remove', ['x'], None))
        def check(_):
            d = self.clusers.master.db.users.getUser('x')
            def real_check(res):
                self.assertEqual(res, None)
            d.addCallback(real_check)
            return d
        d.addCallback(check)
        return d

    def test_perspective_commandline_show(self):
        d = self.call_perspective_commandline('add', None,
                                              [{'identifier':'x', 'a':'c'}])
        d.addCallback(lambda _ :
                          self.call_perspective_commandline('show', ['x'], None))
        def check(_):
            d = self.clusers.master.db.users.getUser('x')
            def real_check(res):
                self.assertEqual(res, dict(identifier='x', a='c', uid=1))
            d.addCallback(real_check)
            return d
        d.addCallback(check)
        return d

    def test_perspective_commandline_add_format(self):
        d = self.call_perspective_commandline('add', None, [{'identifier':'x',
                                                             'a':'b'}])
        def check(result):
            exp_format = "user(s) added:\n\nidentifier: x\nuid: 1\n\n"
            self.assertEqual(result, exp_format)
        d.addCallback(check)
        return d

    def test_perspective_commandline_update_format(self):
        d = self.call_perspective_commandline('add', None, [{'identifier':'x',
                                                             'a':'b'}])
        d.addCallback(lambda _ :
                  self.call_perspective_commandline('update', None,
                                                    [{'identifier':'x','a':'c'}]))
        def check(result):
            exp_format = "user(s) updated:\n\nidentifier: x\na: c\n\n"
            self.assertEqual(result, exp_format)
        d.addCallback(check)
        return d

    def test_perspective_commandline_remove_format(self):
        d = self.call_perspective_commandline('add', None, [{'identifier':'x',
                                                             'a':'b'}])
        d.addCallback(lambda _ :
                          self.call_perspective_commandline('remove', ['x'], None))
        def check(result):
            exp_format = "user(s) removed:\n\na: b\nidentifier: x\nuid: 1\n\n"
            self.assertEqual(result, exp_format)
        d.addCallback(check)
        return d

    def test_perspective_commandline_show_format(self):
        d = self.call_perspective_commandline('add', None, [{'identifier':'x',
                                                             'a':'b'}])
        d.addCallback(lambda _ :
                          self.call_perspective_commandline('show', ['x'], None))
        def check(result):
            exp_format = "user(s) to show:\n\na: b\nidentifier: x\nuid: 1\n\n"
            self.assertEqual(result, exp_format)
        d.addCallback(check)
        return d

    def test_perspective_commandline_remove_no_match_format(self):
        d = self.call_perspective_commandline('remove', ['x'], None)
        def check(result):
            exp_format = "user(s) removed:\n\nno match found\n\n"
            self.assertEqual(result, exp_format)
        d.addCallback(check)
        return d

    def test_perspective_commandline_show_no_match_format(self):
        d = self.call_perspective_commandline('show', ['x'], None)
        def check(result):
            exp_format = "user(s) to show:\n\nno match found\n\n"
            self.assertEqual(result, exp_format)
        d.addCallback(check)
        return d

class TestCommandline_Users(unittest.TestCase, users.ManualUsersMixin):

    def setUp(self):
        self.setUpManualUsers()
        self.clusers = self.attachManualUsers(manual.Commandline_Users())

    def tearDown(self):
        self.tearDownManualUsers()

    def test_service(self):
        # patch out the pbmanager's 'register' command both to be sure
        # the registration is correct and to get a copy of the factory
        registration = mock.Mock()
        registration.unregister = lambda : defer.succeed(None)
        self.clusers.master.pbmanager = mock.Mock()
        def register(portstr, user, passwd, factory):
            self.assertEqual([portstr, user, passwd],
                             [9989, 'user', 'userpw'])
            self.got_factory = factory
            return registration
        self.clusers.master.pbmanager.register = register

        self.clusers.startService()

        persp = self.got_factory(mock.Mock(), 'user')
        self.failUnless(isinstance(persp, manual.Commandline_Users_Perspective))

        return self.clusers.stopService()
