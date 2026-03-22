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

from __future__ import annotations

from twisted.trial import unittest

from buildbot.util import giturlparse


class Tests(unittest.TestCase):
    def test_github(self) -> None:
        for u in [
            "https://github.com/buildbot/buildbot",
            "https://github.com/buildbot/buildbot.git",
            "ssh://git@github.com:buildbot/buildbot.git",
            "git://github.com/buildbot/buildbot.git",
        ]:
            parsed = giturlparse(u)
            assert parsed is not None
            self.assertIn(parsed.user, (None, "git"))
            self.assertEqual(parsed.domain, "github.com")
            self.assertEqual(parsed.owner, "buildbot")
            self.assertEqual(parsed.repo, "buildbot")
            self.assertIsNone(parsed.port)

    def test_gitlab(self) -> None:
        for u in [
            "ssh://git@mygitlab.com/group/subgrouptest/testproject.git",
            "https://mygitlab.com/group/subgrouptest/testproject.git",
            "git@mygitlab.com:group/subgrouptest/testproject.git",
            "git://mygitlab.com/group/subgrouptest/testproject.git",
        ]:
            parsed = giturlparse(u)
            assert parsed is not None
            self.assertIsNone(parsed.port)
            self.assertIn(parsed.user, (None, "git"))
            self.assertEqual(parsed.domain, "mygitlab.com")
            self.assertEqual(parsed.owner, "group/subgrouptest")
            self.assertEqual(parsed.repo, "testproject")

    def test_gitlab_subsubgroup(self) -> None:
        for u in [
            "ssh://git@mygitlab.com/group/subgrouptest/subsubgroup/testproject.git",
            "https://mygitlab.com/group/subgrouptest/subsubgroup/testproject.git",
            "git://mygitlab.com/group/subgrouptest/subsubgroup/testproject.git",
        ]:
            parsed = giturlparse(u)
            assert parsed is not None
            self.assertIn(parsed.user, (None, "git"))
            self.assertIsNone(parsed.port)
            self.assertEqual(parsed.domain, "mygitlab.com")
            self.assertEqual(parsed.owner, "group/subgrouptest/subsubgroup")
            self.assertEqual(parsed.repo, "testproject")

    def test_gitlab_user(self) -> None:
        for u in [
            "ssh://buildbot@mygitlab.com:group/subgrouptest/testproject.git",
            "https://buildbot@mygitlab.com/group/subgrouptest/testproject.git",
        ]:
            parsed = giturlparse(u)
            assert parsed is not None
            self.assertEqual(parsed.domain, "mygitlab.com")
            self.assertIsNone(parsed.port)
            self.assertEqual(parsed.user, "buildbot")
            self.assertEqual(parsed.owner, "group/subgrouptest")
            self.assertEqual(parsed.repo, "testproject")

    def test_gitlab_port(self) -> None:
        for u in ["ssh://buildbot@mygitlab.com:1234/group/subgrouptest/testproject.git"]:
            parsed = giturlparse(u)
            assert parsed is not None
            self.assertEqual(parsed.domain, "mygitlab.com")
            self.assertEqual(parsed.port, 1234)
            self.assertEqual(parsed.user, "buildbot")
            self.assertEqual(parsed.owner, "group/subgrouptest")
            self.assertEqual(parsed.repo, "testproject")

    def test_bitbucket(self) -> None:
        for u in [
            "https://bitbucket.org/org/repo.git",
            "ssh://git@bitbucket.org:org/repo.git",
            "git@bitbucket.org:org/repo.git",
        ]:
            parsed = giturlparse(u)
            assert parsed is not None
            self.assertIn(parsed.user, (None, "git"))
            self.assertEqual(parsed.domain, "bitbucket.org")
            self.assertEqual(parsed.owner, "org")
            self.assertEqual(parsed.repo, "repo")

    def test_no_owner(self) -> None:
        for u in [
            "https://example.org/repo.git",
            "ssh://example.org:repo.git",
            "ssh://git@example.org:repo.git",
            "git@example.org:repo.git",
        ]:
            parsed = giturlparse(u)
            assert parsed is not None
            self.assertIn(parsed.user, (None, "git"))
            self.assertEqual(parsed.domain, "example.org")
            self.assertIsNone(parsed.owner)
            self.assertEqual(parsed.repo, "repo")

    def test_protos(self) -> None:
        self.assertEqual(giturlparse("https://bitbucket.org/org/repo.git").proto, "https")  # type: ignore[union-attr]
        self.assertEqual(giturlparse("git://bitbucket.org/org/repo.git").proto, "git")  # type: ignore[union-attr]
        self.assertEqual(giturlparse("ssh://git@bitbucket.org:org/repo.git").proto, "ssh")  # type: ignore[union-attr]
        self.assertEqual(giturlparse("git@bitbucket.org:org/repo.git").proto, "ssh")  # type: ignore[union-attr]

    def test_user_password(self) -> None:
        for u, expected_user, expected_password in [
            ("https://user@github.com/buildbot/buildbot", "user", None),
            ("https://user:password@github.com/buildbot/buildbot", "user", "password"),
        ]:
            parsed = giturlparse(u)
            assert parsed is not None
            self.assertEqual(parsed.user, expected_user)
            self.assertEqual(parsed.password, expected_password)
            self.assertEqual(parsed.domain, "github.com")
            self.assertEqual(parsed.owner, "buildbot")
            self.assertEqual(parsed.repo, "buildbot")
            self.assertIsNone(parsed.port)
