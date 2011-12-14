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
from twisted.python import components

from buildbot.interfaces import IProperties
from buildbot.process.properties import Properties, PropertiesMixin
from buildbot.status import status_gerrit
from buildbot.status.results import Results, SUCCESS
from buildbot.util import gerrit


class FakeBuild(PropertiesMixin):
    def __init__(self, properties):
        self.properties = properties

components.registerAdapter(
        lambda build: IProperties(build.properties),
        FakeBuild, IProperties)


class TestStatusGerrit(unittest.TestCase):
    """
    Test that GerritStatusPush
    """

    def createFakeGerritConnectionFactory(self, connect_list):
        class FakeGerritConnectionFactory(gerrit.GerritConnectionFactory):

            def connect(slf, gerrit_command):
                args = slf.command_root + gerrit_command
                connect_list.append(args)
        return FakeGerritConnectionFactory

    def setUp(self):
        self.reviewArg = {'hi': 'mom'}
        self.props = Properties()
        self.build = FakeBuild(self.props)
        self.connectList = []
        self.gsp = status_gerrit.GerritStatusPush('server', 'username',
            reviewCB=self.reviewCB, reviewArg=self.reviewArg,
            ConnectionFactoryClass=self.createFakeGerritConnectionFactory(self.connectList))

    def reviewCB(self, builderName, build, result, arg):
        pattern = "%s: %s, %s" % (builderName, Results[result].upper(), arg)
        verified = 1 if result == 0 else -1
        return pattern, verified, 0

    def testSendCodeReview(self):
        self.gsp.sendCodeReview("proj", "rev", message="msg", verified=1,
                                reviewed=1)
        self.assertEqual(1, len(self.connectList))

        expected_connect = ['ssh', 'username@server', '-p', '29418', 'gerrit', 'review',
                           '--project proj', "--message 'msg'", '--verified 1',
                           '--code-review 1', 'rev']
        self.assertEqual(self.connectList.pop(), expected_connect)

    def testGitBuildFinishedSuccess(self):
        self.props.setProperty("project", "proj", "test")
        self.props.setProperty("got_revision", "rev", "test")
        self.gsp.buildFinished("builder", self.build, SUCCESS)
        expectedConnects = []  # should not connect for builds w/o gerrit info
        self.assertEqual(expectedConnects, self.connectList)

    def testGerritBuildFinishedSuccess(self):
        self.props.setProperty("gerrit_branch", "branch", "test")
        self.props.setProperty("project", "proj", "test")
        self.props.setProperty("got_revision", "rev", "test")
        self.gsp.buildFinished("builder", self.build, SUCCESS)

        self.assertEqual(1, len(self.connectList))

        expected_message = "--message 'builder: SUCCESS, {\"hi\": \"mom\"}'"
        expected_connect = ['ssh', 'username@server', '-p', '29418', 'gerrit', 'review',
                           '--project proj', expected_message, '--verified 1', 'rev']
        self.assertEqual(self.connectList.pop(), expected_connect)
