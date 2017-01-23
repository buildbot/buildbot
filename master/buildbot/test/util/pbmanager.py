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

import mock

from twisted.internet import defer


class PBManagerMixin:

    def setUpPBChangeSource(self):
        "Set up a fake self.pbmanager."
        self.registrations = []
        self.unregistrations = []
        pbm = self.pbmanager = mock.Mock()
        pbm.register = self._fake_register

    def _fake_register(self, portstr, username, password, factory):
        reg = mock.Mock()

        def unregister():
            self.unregistrations.append((portstr, username, password))
            return defer.succeed(None)
        reg.unregister = unregister
        self.registrations.append((portstr, username, password))
        return reg

    def assertNotRegistered(self):
        self.assertEqual(self.registrations, [])

    def assertNotUnregistered(self):
        self.assertEqual(self.unregistrations, [])

    def assertRegistered(self, portstr, username, password):
        for ps, un, pw in self.registrations:
            if ps == portstr and username == un and pw == password:
                return
        self.fail("not registered: %r not in %s" %
                  ((portstr, username, password), self.registrations))

    def assertUnregistered(self, portstr, username, password):
        for ps, un, pw in self.unregistrations:
            if ps == portstr and username == un and pw == password:
                return
        self.fail("still registered")
