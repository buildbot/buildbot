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

from buildbot.process.properties import WithProperties
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.steps import cppcheck
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps


class Cppcheck(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_success(self):
        self.setupStep(cppcheck.Cppcheck(enable=['all'], inconclusive=True))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=[
                        'cppcheck', '.', '--enable=all', '--inconclusive']) +
            ExpectShell.log('stdio', stdout='Checking file1.c...') +
            0)
        self.expectOutcome(result=SUCCESS, state_string="cppcheck")
        return self.runStep()

    def test_warnings(self):
        self.setupStep(
            cppcheck.Cppcheck(source=['file1.c'], enable=['warning', 'performance']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=[
                        'cppcheck', 'file1.c', '--enable=warning,performance']) +
            ExpectShell.log(
                'stdio',
                stdout=('Checking file1.c...\n'
                        '[file1.c:3]: (warning) Logical disjunction always evaluates to true: t >= 0 || t < 65.\n'
                        '(information) Cppcheck cannot find all the include files (use --check-config for details)')) +
            0)
        self.expectOutcome(result=WARNINGS,
                           state_string="cppcheck warning=1 information=1 (warnings)")
        return self.runStep()

    def test_errors(self):
        self.setupStep(cppcheck.Cppcheck(extra_args=['--my-param=5']))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=[
                        'cppcheck', '.', '--my-param=5']) +
            ExpectShell.log(
                'stdio',
                stdout=('Checking file1.c...\n'
                        '[file1.c:3]: (error) Possible null pointer dereference: filter\n'
                        '[file1.c:4]: (error) Memory leak: columns\n'
                        "[file1.c:7]: (style) The scope of the variable 'pid' can be reduced")) +
            0)
        self.expectOutcome(result=FAILURE,
                           state_string="cppcheck error=2 style=1 (failure)")
        return self.runStep()

    def test_renderables(self):
        P = WithProperties
        self.setupStep(cppcheck.Cppcheck(
            binary=P('a'), source=[P('.'), P('f.c')], extra_args=[P('--p'), P('--p')]))
        self.expectCommands(
            ExpectShell(workdir='wkdir', command=[
                        'a', '.', 'f.c', '--p', '--p']) +
            ExpectShell.log(
                'stdio',
                stdout='Checking file1.c...') +
            0)
        self.expectOutcome(result=SUCCESS, state_string="cppcheck")
        return self.runStep()
