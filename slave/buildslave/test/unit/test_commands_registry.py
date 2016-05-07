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

from buildslave.commands import registry
from buildslave.commands import shell


class Registry(unittest.TestCase):

    def test_getFactory(self):
        factory = registry.getFactory('shell')
        self.assertEqual(factory, shell.SlaveShellCommand)

    def test_getFactory_KeyError(self):
        self.assertRaises(
            KeyError, lambda: registry.getFactory('nosuchcommand'))

    def test_getAllCommandNames(self):
        self.failUnless('shell' in registry.getAllCommandNames())

    def test_all_commands_exist(self):
        # if this doesn't raise a KeyError, then we're good
        for n in registry.getAllCommandNames():
            registry.getFactory(n)
