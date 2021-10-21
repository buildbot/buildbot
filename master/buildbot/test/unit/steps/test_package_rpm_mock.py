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

from buildbot import config
from buildbot.process.properties import Interpolate
from buildbot.process.results import SUCCESS
from buildbot.steps.package.rpm import mock
from buildbot.test.fake.remotecommand import ExpectRmdir
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps
from buildbot.test.util.misc import TestReactorMixin


class TestMock(steps.BuildStepMixin, TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_no_root(self):
        with self.assertRaises(config.ConfigErrors):
            mock.Mock()

    def test_class_attrs(self):
        step = self.setup_step(mock.Mock(root='TESTROOT'))
        self.assertEqual(step.command, ['mock', '--root', 'TESTROOT'])

    def test_success(self):
        self.setup_step(mock.Mock(root='TESTROOT'))
        self.expectCommands(
            ExpectRmdir(dir=['build/build.log', 'build/root.log', 'build/state.log'],
                        logEnviron=False)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['mock', '--root', 'TESTROOT'],
                        logfiles={'build.log': 'build.log',
                                  'root.log': 'root.log',
                                  'state.log': 'state.log'})
            .exit(0))
        self.expectOutcome(result=SUCCESS, state_string="'mock --root ...'")
        return self.run_step()

    def test_resultdir_success(self):
        self.setup_step(mock.Mock(root='TESTROOT', resultdir='RESULT'))
        self.expectCommands(
            ExpectRmdir(dir=['build/RESULT/build.log',
                             'build/RESULT/root.log',
                             'build/RESULT/state.log'],
                        logEnviron=False)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['mock', '--root', 'TESTROOT',
                                 '--resultdir', 'RESULT'],
                        logfiles={'build.log': 'RESULT/build.log',
                                  'root.log': 'RESULT/root.log',
                                  'state.log': 'RESULT/state.log'})
            .exit(0))
        self.expectOutcome(result=SUCCESS)
        return self.run_step()

    def test_resultdir_renderable(self):
        resultdir_text = "RESULT"
        self.setup_step(mock.Mock(root='TESTROOT', resultdir=Interpolate(
            '%(kw:resultdir)s', resultdir=resultdir_text)))
        self.expectCommands(
            ExpectRmdir(dir=['build/RESULT/build.log',
                             'build/RESULT/root.log',
                             'build/RESULT/state.log'],
                        logEnviron=False)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['mock', '--root', 'TESTROOT',
                                 '--resultdir', 'RESULT'],
                        logfiles={'build.log': 'RESULT/build.log',
                                  'root.log': 'RESULT/root.log',
                                  'state.log': 'RESULT/state.log'})
            .exit(0))
        self.expectOutcome(result=SUCCESS, state_string="'mock --root ...'")
        return self.run_step()


class TestMockBuildSRPM(steps.BuildStepMixin, TestReactorMixin,
                        unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_no_spec(self):
        with self.assertRaises(config.ConfigErrors):
            mock.MockBuildSRPM(root='TESTROOT')

    def test_success(self):
        self.setup_step(mock.MockBuildSRPM(root='TESTROOT', spec="foo.spec"))
        self.expectCommands(
            ExpectRmdir(dir=['build/build.log', 'build/root.log', 'build/state.log'],
                        logEnviron=False)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['mock', '--root', 'TESTROOT',
                                 '--buildsrpm', '--spec', 'foo.spec',
                                 '--sources', '.'],
                        logfiles={'build.log': 'build.log',
                                  'root.log': 'root.log',
                                  'state.log': 'state.log'},)
            .exit(0))
        self.expectOutcome(result=SUCCESS, state_string='mock buildsrpm')
        return self.run_step()


class TestMockRebuild(steps.BuildStepMixin, TestReactorMixin,
                      unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_no_srpm(self):
        with self.assertRaises(config.ConfigErrors):
            mock.MockRebuild(root='TESTROOT')

    def test_success(self):
        self.setup_step(mock.MockRebuild(root='TESTROOT', srpm="foo.src.rpm"))
        self.expectCommands(
            ExpectRmdir(dir=['build/build.log', 'build/root.log', 'build/state.log'],
                        logEnviron=False)
            .exit(0),
            ExpectShell(workdir='wkdir',
                        command=['mock', '--root', 'TESTROOT',
                                 '--rebuild', 'foo.src.rpm'],
                        logfiles={'build.log': 'build.log',
                                  'root.log': 'root.log',
                                  'state.log': 'state.log'},)
            .exit(0))
        self.expectOutcome(result=SUCCESS, state_string='mock rebuild srpm')
        return self.run_step()
