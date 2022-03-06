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

import os
import pprint
import sys

from twisted.internet import defer
from twisted.python import runtime
from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.process.properties import Property
from buildbot.process.properties import renderer
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps import master
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.steps import ExpectMasterShell
from buildbot.test.steps import TestBuildStepMixin

_COMSPEC_ENV = 'COMSPEC'


class TestMasterShellCommand(TestBuildStepMixin, TestReactorMixin,
                             unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        if runtime.platformType == 'win32':
            self.comspec = os.environ.get(_COMSPEC_ENV)
            os.environ[_COMSPEC_ENV] = r'C:\WINDOWS\system32\cmd.exe'
        return self.setup_test_build_step()

    def tearDown(self):
        if runtime.platformType == 'win32':
            if self.comspec:
                os.environ[_COMSPEC_ENV] = self.comspec
            else:
                del os.environ[_COMSPEC_ENV]
        return self.tear_down_test_build_step()

    def test_constr_args(self):
        self.setup_step(
            master.MasterShellCommand(description='x', descriptionDone='y',
                                      env={'a': 'b'}, workdir='build', usePTY=True,
                                      command='true'))

        if runtime.platformType == 'win32':
            exp_argv = [r'C:\WINDOWS\system32\cmd.exe', '/c', 'true']
        else:
            exp_argv = ['/bin/sh', '-c', 'true']

        self.expect_commands(
            ExpectMasterShell(exp_argv)
            .workdir('build')
            .env({'a': 'b'})
            .stdout(b'hello!\n')
            .stderr(b'world\n')
            .exit(0))

        self.expect_log_file('stdio', "hello!\n")
        self.expect_outcome(result=SUCCESS, state_string='y')
        return self.run_step()

    @defer.inlineCallbacks
    def test_env_subst(self):
        os.environ['WORLD'] = 'hello'
        self.setup_step(
            master.MasterShellCommand(command='true', env={'HELLO': '${WORLD}'}))

        if runtime.platformType == 'win32':
            exp_argv = [r'C:\WINDOWS\system32\cmd.exe', '/c', 'true']
        else:
            exp_argv = ['/bin/sh', '-c', 'true']

        self.expect_commands(
            ExpectMasterShell(exp_argv)
            .env({'HELLO': 'hello'})
            .exit(0))

        self.expect_outcome(result=SUCCESS)

        try:
            yield self.run_step()
        finally:
            del os.environ['WORLD']

    @defer.inlineCallbacks
    def test_env_list_subst(self):
        os.environ['WORLD'] = 'hello'
        os.environ['LIST'] = 'world'
        self.setup_step(master.MasterShellCommand(command='true',
                                                  env={'HELLO': ['${WORLD}', '${LIST}']}))

        if sys.platform == 'win32':
            exp_argv = [r'C:\WINDOWS\system32\cmd.exe', '/c', 'true']
            exp_env = 'hello;world'
        else:
            exp_argv = ['/bin/sh', '-c', 'true']
            exp_env = 'hello:world'

        self.expect_commands(
            ExpectMasterShell(exp_argv)
            .env({'HELLO': exp_env})
            .exit(0))

        self.expect_outcome(result=SUCCESS)

        try:
            yield self.run_step()
        finally:
            del os.environ['WORLD']
            del os.environ['LIST']

    def test_prop_rendering(self):
        self.setup_step(master.MasterShellCommand(command=Interpolate('%(prop:project)s-BUILD'),
                                                  workdir='build'))
        self.properties.setProperty("project", "BUILDBOT-TEST", "TEST")

        if runtime.platformType == 'win32':
            exp_argv = [r'C:\WINDOWS\system32\cmd.exe', '/c', 'BUILDBOT-TEST-BUILD']
        else:
            exp_argv = ['/bin/sh', '-c', 'BUILDBOT-TEST-BUILD']

        self.expect_commands(
            ExpectMasterShell(exp_argv)
            .workdir('build')
            .exit(0))

        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_constr_args_descriptionSuffix(self):
        self.setup_step(master.MasterShellCommand(description='x', descriptionDone='y',
                                                 descriptionSuffix='z',
                                                 env={'a': 'b'}, workdir='build', usePTY=True,
                                                 command='true'))

        if runtime.platformType == 'win32':
            exp_argv = [r'C:\WINDOWS\system32\cmd.exe', '/c', 'true']
        else:
            exp_argv = ['/bin/sh', '-c', 'true']

        self.expect_commands(
            ExpectMasterShell(exp_argv)
            .workdir('build')
            .env({'a': 'b'})
            .exit(0))

        self.expect_outcome(result=SUCCESS, state_string='y z')
        return self.run_step()


class TestSetProperty(TestBuildStepMixin, TestReactorMixin,
                      unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_simple(self):
        self.setup_step(master.SetProperty(property="testProperty", value=Interpolate(
            "sch=%(prop:scheduler)s, worker=%(prop:workername)s")))
        self.properties.setProperty(
            'scheduler', 'force', source='SetProperty', runtime=True)
        self.properties.setProperty(
            'workername', 'testWorker', source='SetProperty', runtime=True)
        self.expect_outcome(result=SUCCESS, state_string="Set")
        self.expect_property(
            'testProperty', 'sch=force, worker=testWorker', source='SetProperty')
        return self.run_step()


class TestLogRenderable(TestBuildStepMixin, TestReactorMixin,
                        unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_simple(self):
        self.setup_step(master.LogRenderable(
            content=Interpolate('sch=%(prop:scheduler)s, worker=%(prop:workername)s')))
        self.properties.setProperty(
            'scheduler', 'force', source='TestSetProperty', runtime=True)
        self.properties.setProperty(
            'workername', 'testWorker', source='TestSetProperty', runtime=True)
        self.expect_outcome(result=SUCCESS, state_string='Logged')
        self.expect_log_file(
            'Output', pprint.pformat('sch=force, worker=testWorker'))
        return self.run_step()


class TestsSetProperties(TestBuildStepMixin, TestReactorMixin,
                         unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def doOneTest(self, **kwargs):
        # all three tests should create a 'a' property with 'b' value, all with different
        # more or less dynamic methods
        self.setup_step(
            master.SetProperties(name="my-step", **kwargs))
        self.expect_property('a', 'b', 'my-step')
        self.expect_outcome(result=SUCCESS, state_string='Properties Set')
        return self.run_step()

    def test_basic(self):
        return self.doOneTest(properties={'a': 'b'})

    def test_renderable(self):
        return self.doOneTest(properties={'a': Interpolate("b")})

    def test_renderer(self):
        @renderer
        def manipulate(props):
            # the renderer returns renderable!
            return {'a': Interpolate('b')}
        return self.doOneTest(properties=manipulate)


class TestAssert(TestBuildStepMixin, TestReactorMixin,
                 unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        return self.setup_test_build_step()

    def tearDown(self):
        return self.tear_down_test_build_step()

    def test_eq_pass(self):
        self.setup_step(master.Assert(
            Property("test_prop") == "foo"))
        self.properties.setProperty("test_prop", "foo", "bar")
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_eq_fail(self):
        self.setup_step(master.Assert(
            Property("test_prop") == "bar"))
        self.properties.setProperty("test_prop", "foo", "bar")
        self.expect_outcome(result=FAILURE)
        return self.run_step()

    def test_renderable_pass(self):
        @renderer
        def test_renderer(props):
            return props.getProperty("test_prop") == "foo"
        self.setup_step(master.Assert(test_renderer))
        self.properties.setProperty("test_prop", "foo", "bar")
        self.expect_outcome(result=SUCCESS)
        return self.run_step()

    def test_renderable_fail(self):
        @renderer
        def test_renderer(props):
            return props.getProperty("test_prop") == "bar"
        self.setup_step(master.Assert(test_renderer))
        self.properties.setProperty("test_prop", "foo", "bar")
        self.expect_outcome(result=FAILURE)
        return self.run_step()
