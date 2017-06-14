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

import os
import pprint
import sys

from twisted.internet import error
from twisted.internet import reactor
from twisted.python import failure
from twisted.python import runtime
from twisted.trial import unittest

from buildbot.process.properties import Interpolate
from buildbot.process.properties import Property
from buildbot.process.properties import WithProperties
from buildbot.process.properties import renderer
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps import master
from buildbot.test.util import steps

_COMSPEC_ENV = 'COMSPEC'


class TestMasterShellCommand(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        if runtime.platformType == 'win32':
            self.comspec = os.environ.get(_COMSPEC_ENV)
            os.environ[_COMSPEC_ENV] = r'C:\WINDOWS\system32\cmd.exe'
        return self.setUpBuildStep()

    def tearDown(self):
        if runtime.platformType == 'win32':
            if self.comspec:
                os.environ[_COMSPEC_ENV] = self.comspec
            else:
                del os.environ[_COMSPEC_ENV]
        return self.tearDownBuildStep()

    def patchSpawnProcess(self, exp_cmd, exp_argv, exp_path, exp_usePTY,
                          exp_env, outputs):
        def spawnProcess(pp, cmd, argv, path, usePTY, env):
            self.assertEqual([cmd, argv, path, usePTY, env],
                             [exp_cmd, exp_argv, exp_path, exp_usePTY, exp_env])
            for output in outputs:
                if output[0] == 'out':
                    pp.outReceived(output[1])
                elif output[0] == 'err':
                    pp.errReceived(output[1])
                elif output[0] == 'rc':
                    if output[1] != 0:
                        so = error.ProcessTerminated(exitCode=output[1])
                    else:
                        so = error.ProcessDone(None)
                    pp.processEnded(failure.Failure(so))
        self.patch(reactor, 'spawnProcess', spawnProcess)

    def test_real_cmd(self):
        cmd = [sys.executable, '-c', 'print("hello")']
        self.setupStep(
            master.MasterShellCommand(command=cmd))
        if runtime.platformType == 'win32':
            self.expectLogfile('stdio', "hello\r\n")
        else:
            self.expectLogfile('stdio', "hello\n")
        self.expectOutcome(result=SUCCESS, state_string="Ran")
        return self.runStep()

    def test_real_cmd_interrupted(self):
        cmd = [sys.executable, '-c', 'while True: pass']
        self.setupStep(
            master.MasterShellCommand(command=cmd))
        self.expectLogfile('stdio', "")
        if runtime.platformType == 'win32':
            # windows doesn't have signals, so we don't get 'killed',
            # but the "exception" part still works.
            self.expectOutcome(result=EXCEPTION,
                               state_string="failed (1) (exception)")
        else:
            self.expectOutcome(result=EXCEPTION,
                               state_string="killed (9) (exception)")
        d = self.runStep()
        self.step.interrupt("KILL")
        return d

    def test_real_cmd_fails(self):
        cmd = [sys.executable, '-c', 'import sys; sys.exit(1)']
        self.setupStep(
            master.MasterShellCommand(command=cmd))
        self.expectLogfile('stdio', "")
        self.expectOutcome(result=FAILURE, state_string="failed (1) (failure)")
        return self.runStep()

    def test_constr_args(self):
        self.setupStep(
            master.MasterShellCommand(description='x', descriptionDone='y',
                                      env={'a': 'b'}, workdir='build', usePTY=True,
                                      command='true'))

        if runtime.platformType == 'win32':
            exp_argv = [r'C:\WINDOWS\system32\cmd.exe', '/c', 'true']
        else:
            exp_argv = ['/bin/sh', '-c', 'true']
        self.patchSpawnProcess(
            exp_cmd=exp_argv[0], exp_argv=exp_argv,
            exp_path='build', exp_usePTY=True, exp_env={'a': 'b'},
            outputs=[
                ('out', 'hello!\n'),
                ('err', 'world\n'),
                ('rc', 0),
            ])
        self.expectOutcome(result=SUCCESS, state_string='y')
        return self.runStep()

    def test_env_subst(self):
        cmd = [sys.executable, '-c', 'import os; print(os.environ["HELLO"])']
        os.environ['WORLD'] = 'hello'
        self.setupStep(
            master.MasterShellCommand(command=cmd,
                                      env={'HELLO': '${WORLD}'}))
        if runtime.platformType == 'win32':
            self.expectLogfile('stdio', "hello\r\n")
        else:
            self.expectLogfile('stdio', "hello\n")
        self.expectOutcome(result=SUCCESS)

        d = self.runStep()

        @d.addBoth
        def _restore_env(res):
            del os.environ['WORLD']
            return res
        return d

    def test_env_list_subst(self):
        cmd = [sys.executable, '-c', 'import os; print(os.environ["HELLO"])']
        os.environ['WORLD'] = 'hello'
        os.environ['LIST'] = 'world'
        self.setupStep(
            master.MasterShellCommand(command=cmd,
                                      env={'HELLO': ['${WORLD}', '${LIST}']}))
        if runtime.platformType == 'win32':
            self.expectLogfile('stdio', "hello;world\r\n")
        else:
            self.expectLogfile('stdio', "hello:world\n")
        self.expectOutcome(result=SUCCESS)

        d = self.runStep()

        @d.addBoth
        def _restore_env(res):
            del os.environ['WORLD']
            del os.environ['LIST']
            return res
        return d

    def test_prop_rendering(self):
        cmd = [sys.executable, '-c', WithProperties(
            'import os; print("%s"); print(os.environ[\"BUILD\"])',
            'project')]
        self.setupStep(
            master.MasterShellCommand(command=cmd,
                                      env={'BUILD': WithProperties('%s', "project")}))
        self.properties.setProperty("project", "BUILDBOT-TEST", "TEST")
        if runtime.platformType == 'win32':
            self.expectLogfile('stdio', "BUILDBOT-TEST\r\nBUILDBOT-TEST\r\n")
        else:
            self.expectLogfile('stdio', "BUILDBOT-TEST\nBUILDBOT-TEST\n")
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_constr_args_descriptionSuffix(self):
        self.setupStep(
            master.MasterShellCommand(description='x', descriptionDone='y',
                                      descriptionSuffix='z',
                                      env={'a': 'b'}, workdir='build', usePTY=True,
                                      command='true'))

        if runtime.platformType == 'win32':
            exp_argv = [r'C:\WINDOWS\system32\cmd.exe', '/c', 'true']
        else:
            exp_argv = ['/bin/sh', '-c', 'true']
        self.patchSpawnProcess(
            exp_cmd=exp_argv[0], exp_argv=exp_argv,
            exp_path='build', exp_usePTY=True, exp_env={'a': 'b'},
            outputs=[
                ('out', 'hello!\n'),
                ('err', 'world\n'),
                ('rc', 0),
            ])
        self.expectOutcome(result=SUCCESS, state_string='y z')
        return self.runStep()


class TestSetProperty(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_simple(self):
        self.setupStep(master.SetProperty(property="testProperty", value=Interpolate(
            "sch=%(prop:scheduler)s, worker=%(prop:workername)s")))
        self.properties.setProperty(
            'scheduler', 'force', source='SetProperty', runtime=True)
        self.properties.setProperty(
            'workername', 'testWorker', source='SetProperty', runtime=True)
        self.expectOutcome(result=SUCCESS, state_string="Set")
        self.expectProperty(
            'testProperty', 'sch=force, worker=testWorker', source='SetProperty')
        return self.runStep()


class TestLogRenderable(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_simple(self):
        self.setupStep(master.LogRenderable(
            content=Interpolate('sch=%(prop:scheduler)s, worker=%(prop:workername)s')))
        self.properties.setProperty(
            'scheduler', 'force', source='TestSetProperty', runtime=True)
        self.properties.setProperty(
            'workername', 'testWorker', source='TestSetProperty', runtime=True)
        self.expectOutcome(result=SUCCESS, state_string='Logged')
        self.expectLogfile(
            'Output', pprint.pformat('sch=force, worker=testWorker'))
        return self.runStep()


class TestsSetProperties(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def doOneTest(self, **kwargs):
        # all three tests should create a 'a' property with 'b' value, all with different
        # more or less dynamic methods
        self.setupStep(
            master.SetProperties(name="my-step", **kwargs))
        self.expectProperty('a', 'b', 'my-step')
        self.expectOutcome(result=SUCCESS, state_string='Properties Set')
        return self.runStep()

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


class TestAssert(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_eq_pass(self):
        self.setupStep(master.Assert(
            Property("test_prop") == "foo"))
        self.properties.setProperty("test_prop", "foo", "bar")
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_eq_fail(self):
        self.setupStep(master.Assert(
            Property("test_prop") == "bar"))
        self.properties.setProperty("test_prop", "foo", "bar")
        self.expectOutcome(result=FAILURE)
        return self.runStep()

    def test_renderable_pass(self):
        @renderer
        def test_renderer(props):
            return props.getProperty("test_prop") == "foo"
        self.setupStep(master.Assert(test_renderer))
        self.properties.setProperty("test_prop", "foo", "bar")
        self.expectOutcome(result=SUCCESS)
        return self.runStep()

    def test_renderable_fail(self):
        @renderer
        def test_renderer(props):
            return props.getProperty("test_prop") == "bar"
        self.setupStep(master.Assert(test_renderer))
        self.properties.setProperty("test_prop", "foo", "bar")
        self.expectOutcome(result=FAILURE)
        return self.runStep()
