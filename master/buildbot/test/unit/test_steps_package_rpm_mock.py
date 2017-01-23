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
from buildbot.process.properties import Interpolate
from buildbot.process.results import SUCCESS
from buildbot.steps.package.rpm import mock
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import steps


class TestMock(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_no_root(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          mock.Mock())

    def test_class_attrs(self):
        step = self.setupStep(mock.Mock(root='TESTROOT'))
        self.assertEqual(step.command, ['mock', '--root', 'TESTROOT'])

    def test_success(self):
        self.setupStep(mock.Mock(root='TESTROOT'))
        self.expectCommands(
            Expect('rmdir', {'dir': ['build/build.log', 'build/root.log',
                                     'build/state.log']})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mock', '--root', 'TESTROOT'],
                        logfiles={'build.log': 'build.log',
                                  'root.log': 'root.log',
                                  'state.log': 'state.log'})
            + 0)
        self.expectOutcome(result=SUCCESS, state_string="'mock --root ...'")
        return self.runStep()

    def test_resultdir_success(self):
        self.setupStep(mock.Mock(root='TESTROOT', resultdir='RESULT'))
        self.expectCommands(
            Expect('rmdir', {'dir': ['build/RESULT/build.log',
                                     'build/RESULT/root.log',
                                     'build/RESULT/state.log']})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mock', '--root', 'TESTROOT',
                                 '--resultdir', 'RESULT'],
                        logfiles={'build.log': 'RESULT/build.log',
                                  'root.log': 'RESULT/root.log',
                                  'state.log': 'RESULT/state.log'})
            + 0)
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_resultdir_renderable(self):
        resultdir_text = "RESULT"
        self.setupStep(mock.Mock(root='TESTROOT', resultdir=Interpolate(
            '%(kw:resultdir)s', resultdir=resultdir_text)))
        self.expectCommands(
            Expect('rmdir', {'dir': ['build/RESULT/build.log',
                                     'build/RESULT/root.log',
                                     'build/RESULT/state.log']})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mock', '--root', 'TESTROOT',
                                 '--resultdir', 'RESULT'],
                        logfiles={'build.log': 'RESULT/build.log',
                                  'root.log': 'RESULT/root.log',
                                  'state.log': 'RESULT/state.log'})
            + 0)
        self.expectOutcome(result=SUCCESS, state_string="'mock --root ...'")
        return self.runStep()


class TestMockBuildSRPM(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_no_spec(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          mock.MockBuildSRPM(root='TESTROOT'))

    def test_success(self):
        self.setupStep(mock.MockBuildSRPM(root='TESTROOT', spec="foo.spec"))
        self.expectCommands(
            Expect('rmdir', {'dir': ['build/build.log', 'build/root.log',
                                     'build/state.log']})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mock', '--root', 'TESTROOT',
                                 '--buildsrpm', '--spec', 'foo.spec',
                                 '--sources', '.'],
                        logfiles={'build.log': 'build.log',
                                  'root.log': 'root.log',
                                  'state.log': 'state.log'},)
            + 0)
        self.expectOutcome(result=SUCCESS, state_string='mock buildsrpm')
        return self.runStep()


class TestMockRebuild(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_no_srpm(self):
        self.assertRaises(config.ConfigErrors, lambda:
                          mock.MockRebuild(root='TESTROOT'))

    def test_success(self):
        self.setupStep(mock.MockRebuild(root='TESTROOT', srpm="foo.src.rpm"))
        self.expectCommands(
            Expect('rmdir', {'dir': ['build/build.log', 'build/root.log',
                                     'build/state.log']})
            + 0,
            ExpectShell(workdir='wkdir',
                        command=['mock', '--root', 'TESTROOT',
                                 '--rebuild', 'foo.src.rpm'],
                        logfiles={'build.log': 'build.log',
                                  'root.log': 'root.log',
                                  'state.log': 'state.log'},)
            + 0)
        self.expectOutcome(result=SUCCESS, state_string='mock rebuild srpm')
        return self.runStep()
