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

from buildbot.process.results import SUCCESS
from buildbot.steps.package.rpm import rpmlint
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import TestBuildStepMixin


class TestRpmLint(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_success(self):
        self.setup_step(rpmlint.RpmLint())
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['rpmlint', '-i', '.'])
            .exit(0))
        self.expect_outcome(
            result=SUCCESS, state_string='Finished checking RPM/SPEC issues')
        return self.run_step()

    def test_fileloc_success(self):
        self.setup_step(rpmlint.RpmLint(fileloc='RESULT'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['rpmlint', '-i', 'RESULT'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_config_success(self):
        self.setup_step(rpmlint.RpmLint(config='foo.cfg'))
        self.expect_commands(
            ExpectShell(workdir='wkdir',
                        command=['rpmlint', '-i', '-f', 'foo.cfg', '.'])
            .exit(0))
        self.expect_outcome(result=SUCCESS)
        return self.run_step()
