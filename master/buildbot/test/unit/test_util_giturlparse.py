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

from buildbot.util import giturlparse


class Tests(unittest.TestCase):

    def test_github(self):
        for u in [
                "https://github.com/buildbot/buildbot",
                "https://github.com/buildbot/buildbot.git",
                "ssh://git@github.com:buildbot/buildbot.git",
                "git://github.com/buildbot/buildbot.git"]:
            u = giturlparse(u)
            self.assertIn(u.user, (None, "git"))
            self.assertEqual(u.domain, "github.com")
            self.assertEqual(u.owner, "buildbot")
            self.assertEqual(u.repo, "buildbot")

    def test_gitlab(self):
        for u in [
                "ssh://git@mygitlab.com/group/subgrouptest/testproject.git",
                "https://mygitlab.com/group/subgrouptest/testproject.git",
                "git@mygitlab.com:group/subgrouptest/testproject.git",
                "git://mygitlab.com/group/subgrouptest/testproject.git"]:
            u = giturlparse(u)
            self.assertIn(u.user, (None, "git"))
            self.assertEqual(u.domain, "mygitlab.com")
            self.assertEqual(u.owner, "group/subgrouptest")
            self.assertEqual(u.repo, "testproject")

    def test_gitlab_subsubgroup(self):
        for u in [
                "ssh://git@mygitlab.com/group/subgrouptest/subsubgroup/testproject.git",
                "https://mygitlab.com/group/subgrouptest/subsubgroup/testproject.git",
                "git://mygitlab.com/group/subgrouptest/subsubgroup/testproject.git"]:
            u = giturlparse(u)
            self.assertIn(u.user, (None, "git"))
            self.assertEqual(u.domain, "mygitlab.com")
            self.assertEqual(u.owner, "group/subgrouptest/subsubgroup")
            self.assertEqual(u.repo, "testproject")

    def test_gitlab_user(self):
        for u in [
                "ssh://buildbot@mygitlab.com:group/subgrouptest/testproject.git",
                "https://buildbot@mygitlab.com/group/subgrouptest/testproject.git"]:
            u = giturlparse(u)
            self.assertEqual(u.domain, "mygitlab.com")
            self.assertEqual(u.user, "buildbot")
            self.assertEqual(u.owner, "group/subgrouptest")
            self.assertEqual(u.repo, "testproject")

    def test_gitlab_port(self):
        for u in [
                "ssh://buildbot@mygitlab.com:1234/group/subgrouptest/testproject.git"]:
            u = giturlparse(u)
            self.assertEqual(u.domain, "mygitlab.com")
            self.assertEqual(u.port, 1234)
            self.assertEqual(u.user, "buildbot")
            self.assertEqual(u.owner, "group/subgrouptest")
            self.assertEqual(u.repo, "testproject")

    def test_bitbucket(self):
        for u in [
                "https://bitbucket.org/org/repo.git",
                "ssh://git@bitbucket.org:org/repo.git",
                "git@bitbucket.org:org/repo.git",
                ]:
            u = giturlparse(u)
            self.assertIn(u.user, (None, "git"))
            self.assertEqual(u.domain, "bitbucket.org")
            self.assertEqual(u.owner, "org")
            self.assertEqual(u.repo, "repo")

    def test_protos(self):
        self.assertEqual(giturlparse("https://bitbucket.org/org/repo.git").proto, "https")
        self.assertEqual(giturlparse("git://bitbucket.org/org/repo.git").proto, "git")
        self.assertEqual(giturlparse("ssh://git@bitbucket.org:org/repo.git").proto, "ssh")
        self.assertEqual(giturlparse("git@bitbucket.org:org/repo.git").proto, "ssh")
