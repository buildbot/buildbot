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

from buildbot.status.results import FAILURE
from buildbot.status.results import SUCCESS
from buildbot.status.status_stash import StashStatusPush, INPROGRESS, SUCCESSFUL, FAILED
from buildbot.test.fake.fakebuild import FakeBuild
from buildbot.test.util import logging
from mock import Mock
from twisted.trial import unittest


class TestStashStatusPush(unittest.TestCase, logging.LoggingMixin):

    def setUp(self):
        super(TestStashStatusPush, self).setUp()

        self.setUpLogging()
        self.build = FakeBuild()
        self.status = StashStatusPush('fake host', 'fake user', 'fake password')

    def tearDown(self):
        pass

    def test_buildStarted_sends_inprogress(self):
        """
        buildStarted should send INPROGRESS
        """
        self.status.send = Mock()
        self.status.buildStarted('fakeBuilderName', self.build)
        self.status.send.assert_called_with('fakeBuilderName', self.build, INPROGRESS)

    def test_buildFinished_sends_successful_on_success(self):
        """
        buildFinished should send SUCCESSFUL if called with SUCCESS
        """
        self.status.send = Mock()
        self.status.buildFinished('fakeBuilderName', self.build, SUCCESS)
        self.status.send.assert_called_with('fakeBuilderName', self.build, SUCCESSFUL)

    def test_buildFinished_sends_failed_on_failure(self):
        """
        buildFinished should send FAILED if called with anything other than SUCCESS
        """
        self.status.send = Mock()
        self.status.buildFinished('fakeBuilderName', self.build, FAILURE)
        self.status.send.assert_called_with('fakeBuilderName', self.build, FAILED)
