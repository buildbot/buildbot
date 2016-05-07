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

from buildbot.www.authz import roles


class RolesFromGroups(unittest.TestCase):

    def setUp(self):
        self.roles = roles.RolesFromGroups("buildbot-")

    def test_noGroups(self):
        ret = self.roles.getRolesFromUser(dict(
            user="homer"))
        self.assertEqual(ret, [])

    def test_noBuildbotGroups(self):
        ret = self.roles.getRolesFromUser(dict(
            user="homer",
            groups=["employee"]))
        self.assertEqual(ret, [])

    def test_someBuildbotGroups(self):
        ret = self.roles.getRolesFromUser(dict(
            user="homer",
            groups=["employee", "buildbot-maintainer", "buildbot-admin"]))
        self.assertEqual(ret, ["maintainer", "admin"])


class RolesFromEmails(unittest.TestCase):

    def setUp(self):
        self.roles = roles.RolesFromEmails(
            employee=["homer@plant.com", "burns@plant.com"], boss=["burns@plant.com"])

    def test_noUser(self):
        ret = self.roles.getRolesFromUser(dict(
            user="lisa", email="lisa@school.com"))
        self.assertEqual(ret, [])

    def test_User1(self):
        ret = self.roles.getRolesFromUser(dict(
            user="homer", email="homer@plant.com"))
        self.assertEqual(ret, ["employee"])

    def test_User2(self):
        ret = self.roles.getRolesFromUser(dict(
            user="burns", email="burns@plant.com"))
        self.assertEqual(sorted(ret), ["boss", "employee"])


class RolesFromOwner(unittest.TestCase):

    def setUp(self):
        self.roles = roles.RolesFromOwner("ownerofbuild")

    def test_noOwner(self):
        ret = self.roles.getRolesFromUser(dict(
            user="lisa", email="lisa@school.com"), None)
        self.assertEqual(ret, [])

    def test_notOwner(self):
        ret = self.roles.getRolesFromUser(dict(
            user="lisa", email="lisa@school.com"), "homer@plant.com")
        self.assertEqual(ret, [])

    def test_owner(self):
        ret = self.roles.getRolesFromUser(dict(
            user="homer", email="homer@plant.com"), "homer@plant.com")
        self.assertEqual(ret, ["ownerofbuild"])
