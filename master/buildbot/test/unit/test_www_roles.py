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

from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.www.authz import roles


class RolesFromGroups(unittest.TestCase):

    def setUp(self):
        self.roles = roles.RolesFromGroups("buildbot-")

    def test_noGroups(self):
        ret = self.roles.getRolesFromUser(dict(
            username="homer"))
        self.assertEqual(ret, [])

    def test_noBuildbotGroups(self):
        ret = self.roles.getRolesFromUser(dict(
            username="homer",
            groups=["employee"]))
        self.assertEqual(ret, [])

    def test_someBuildbotGroups(self):
        ret = self.roles.getRolesFromUser(dict(
            username="homer",
            groups=["employee", "buildbot-maintainer", "buildbot-admin"]))
        self.assertEqual(ret, ["maintainer", "admin"])


class RolesFromEmails(unittest.TestCase):

    def setUp(self):
        self.roles = roles.RolesFromEmails(
            employee=["homer@plant.com", "burns@plant.com"], boss=["burns@plant.com"])

    def test_noUser(self):
        ret = self.roles.getRolesFromUser(dict(
            username="lisa", email="lisa@school.com"))
        self.assertEqual(ret, [])

    def test_User1(self):
        ret = self.roles.getRolesFromUser(dict(
            username="homer", email="homer@plant.com"))
        self.assertEqual(ret, ["employee"])

    def test_User2(self):
        ret = self.roles.getRolesFromUser(dict(
            username="burns", email="burns@plant.com"))
        self.assertEqual(sorted(ret), ["boss", "employee"])


class RolesFromOwner(unittest.TestCase):

    def setUp(self):
        self.roles = roles.RolesFromOwner("ownerofbuild")

    def test_noOwner(self):
        ret = self.roles.getRolesFromUser(dict(
            username="lisa", email="lisa@school.com"), None)
        self.assertEqual(ret, [])

    def test_notOwner(self):
        ret = self.roles.getRolesFromUser(dict(
            username="lisa", email="lisa@school.com"), "homer@plant.com")
        self.assertEqual(ret, [])

    def test_owner(self):
        ret = self.roles.getRolesFromUser(dict(
            username="homer", email="homer@plant.com"), "homer@plant.com")
        self.assertEqual(ret, ["ownerofbuild"])


class RolesFromUsername(unittest.TestCase, ConfigErrorsMixin):

    def setUp(self):
        self.roles = roles.RolesFromUsername(roles=["admins"], usernames=["Admin"])
        self.roles2 = roles.RolesFromUsername(
            roles=["developers", "integrators"], usernames=["Alice", "Bob"])

    def test_anonymous(self):
        ret = self.roles.getRolesFromUser(dict(anonymous=True))
        self.assertEqual(ret, [])

    def test_normalUser(self):
        ret = self.roles.getRolesFromUser(dict(username="Alice"))
        self.assertEqual(ret, [])

    def test_admin(self):
        ret = self.roles.getRolesFromUser(dict(username="Admin"))
        self.assertEqual(ret, ["admins"])

    def test_multipleGroups(self):
        ret = self.roles2.getRolesFromUser(dict(username="Bob"))
        self.assertEqual(ret, ["developers", "integrators"])

    def test_badUsernames(self):
        self.assertRaisesConfigError('Usernames cannot be None',
            lambda: roles.RolesFromUsername(roles=[], usernames=[None]))
