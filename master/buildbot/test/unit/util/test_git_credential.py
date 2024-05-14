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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.properties import Properties
from buildbot.process.properties import Property
from buildbot.test.fake.fakebuild import FakeBuild
from buildbot.util.git_credential import GitCredentialInputRenderer


class TestGitCredentialInputRenderer(unittest.TestCase):
    def setUp(self):
        self.props = Properties()
        self.build = FakeBuild(props=self.props)

    @defer.inlineCallbacks
    def test_render(self):
        self.props.setProperty("password", "property_password", "test")
        renderer = GitCredentialInputRenderer(
            username="user",
            password=Property("password"),
            url="https://example.com/repo.git",
        )
        rendered = yield self.build.render(renderer)
        self.assertEqual(
            rendered,
            "url=https://example.com/repo.git\nusername=user\npassword=property_password\n",
        )
