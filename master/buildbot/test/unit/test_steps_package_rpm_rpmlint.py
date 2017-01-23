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

from buildbot.process.results import SUCCESS
from buildbot.steps.package.rpm import rpmlint
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps


class TestRpmLint(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_success(self):
        self.setupStep(rpmlint.RpmLint())
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['rpmlint', '-i', '.'])
            + 0)
        self.expectOutcome(
            result=SUCCESS, state_string='Finished checking RPM/SPEC issues')
        return self.runStep()

    def test_fileloc_success(self):
        self.setupStep(rpmlint.RpmLint(fileloc='RESULT'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['rpmlint', '-i', 'RESULT'])
            + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_config_success(self):
        self.setupStep(rpmlint.RpmLint(config='foo.cfg'))
        self.expectCommands(
            ExpectShell(workdir='wkdir',
                        command=['rpmlint', '-i', '-f', 'foo.cfg', '.'])
            + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()
