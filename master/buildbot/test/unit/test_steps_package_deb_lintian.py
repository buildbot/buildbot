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

from buildbot import config
from buildbot.process.results import SUCCESS
from buildbot.steps.package.deb import lintian
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps


class TestDebLintian(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_no_fileloc(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          lintian.DebLintian())

    def test_success(self):
        self.setupStep(lintian.DebLintian('foo_0.23_i386.changes'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['lintian', '-v', 'foo_0.23_i386.changes']) +
            0)
        self.expectOutcome(result=SUCCESS, state_string="Lintian")
        return self.runStep()

    def test_success_suppressTags(self):
        self.setupStep(lintian.DebLintian('foo_0.23_i386.changes',
                                          suppressTags=['bad-distribution-in-changes-file']))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['lintian', '-v', 'foo_0.23_i386.changes',
                                 '--suppress-tags', 'bad-distribution-in-changes-file']) +
            0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()
