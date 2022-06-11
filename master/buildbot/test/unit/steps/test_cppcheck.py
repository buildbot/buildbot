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

from buildbot.process.properties import WithProperties
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.steps import cppcheck
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectShell
from buildbot.test.steps import TestBuildStepMixin


class Cppcheck(TestBuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_success(self):
        self.setup_step(cppcheck.Cppcheck(enable=['all'], inconclusive=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=[
                        'cppcheck', '.', '--enable=all', '--inconclusive'])
            .stdout('Checking file1.c...')
            .exit(0))
        self.expect_outcome(result=SUCCESS, state_string="cppcheck")
        return self.run_step()

    def test_command_failure(self):
        self.setup_step(cppcheck.Cppcheck(enable=['all'], inconclusive=True))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=[
                        'cppcheck', '.', '--enable=all', '--inconclusive'])
            .stdout('Checking file1.c...')
            .exit(1))
        self.expect_outcome(result=FAILURE, state_string="cppcheck (failure)")
        return self.run_step()

    def test_warnings(self):
        self.setup_step(
            cppcheck.Cppcheck(source=['file1.c'], enable=['warning', 'performance']))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=[
                        'cppcheck', 'file1.c', '--enable=warning,performance'])
            .stdout('Checking file1.c...\n'
                    '[file1.c:3]: (warning) Logical disjunction always '
                    'evaluates to true: t >= 0 || t < 65.\n'
                    '(information) Cppcheck cannot find all the include files '
                    '(use --check-config for details)')
            .exit(0))
        self.expect_outcome(result=WARNINGS,
                           state_string="cppcheck warning=1 information=1 (warnings)")
        return self.run_step()

    def test_errors(self):
        self.setup_step(cppcheck.Cppcheck(extra_args=['--my-param=5']))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=[
                        'cppcheck', '.', '--my-param=5'])
            .stdout('Checking file1.c...\n'
                    '[file1.c:3]: (error) Possible null pointer dereference: filter\n'
                    '[file1.c:4]: (error) Memory leak: columns\n'
                    "[file1.c:7]: (style) The scope of the variable 'pid' can be reduced")
            .exit(0))
        self.expect_outcome(result=FAILURE,
                           state_string="cppcheck error=2 style=1 (failure)")
        return self.run_step()

    def test_renderables(self):
        P = WithProperties
        self.setup_step(cppcheck.Cppcheck(
            binary=P('a'), source=[P('.'), P('f.c')], extra_args=[P('--p'), P('--p')]))
        self.expect_commands(
            ExpectShell(workdir='wkdir', command=[
                        'a', '.', 'f.c', '--p', '--p'])
            .stdout('Checking file1.c...')
            .exit(0))
        self.expect_outcome(result=SUCCESS, state_string="cppcheck")
        return self.run_step()
