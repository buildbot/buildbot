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

from buildbot.process.properties import Interpolate
from buildbot.process.properties import WithProperties
from buildbot.status.results import EXCEPTION
from buildbot.status.results import FAILURE
from buildbot.status.results import SUCCESS
from buildbot.steps import master
from buildbot.test.util import steps
from twisted.internet import error
from twisted.internet import reactor
from twisted.python import failure
from twisted.python import runtime
from twisted.python.filepath import FilePath
from twisted.trial import unittest


class TestMasterShellCommand(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        if runtime.platformType == 'win32':
            self.comspec = os.environ.get('COMPSPEC')
            os.environ['COMSPEC'] = r'C:\WINDOWS\system32\cmd.exe'
        return self.setUpBuildStep()

    def tearDown(self):
        if runtime.platformType == 'win32':
            if self.comspec:
                os.environ['COMSPEC'] = self.comspec
            else:
                del os.environ['COMSPEC']
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
        cmd = [sys.executable, '-c', 'print "hello"']
        self.setupStep(
            master.MasterShellCommand(command=cmd))
        if runtime.platformType == 'win32':
            self.expectLogfile('stdio', "hello\r\n")
        else:
            self.expectLogfile('stdio', "hello\n")
        self.expectOutcome(result=SUCCESS, status_text=["Ran"])
        return self.runStep()

    def test_real_cmd_interrupted(self):
        cmd = [sys.executable, '-c', 'while True: pass']
        self.setupStep(
            master.MasterShellCommand(command=cmd))
        self.expectLogfile('stdio', "")
        if runtime.platformType == 'win32':
            # windows doesn't have signals, so we don't get 'killed'
            self.expectOutcome(result=EXCEPTION,
                               status_text=["failed (1)", "interrupted"])
        else:
            self.expectOutcome(result=EXCEPTION,
                               status_text=["killed (9)", "interrupted"])
        d = self.runStep()
        self.step.interrupt("KILL")
        return d

    def test_real_cmd_fails(self):
        cmd = [sys.executable, '-c', 'import sys; sys.exit(1)']
        self.setupStep(
            master.MasterShellCommand(command=cmd))
        self.expectLogfile('stdio', "")
        self.expectOutcome(result=FAILURE, status_text=["failed (1)"])
        return self.runStep()

    def test_constr_args(self):
        self.setupStep(
            master.MasterShellCommand(description='x', descriptionDone='y',
                                      env={'a': 'b'}, path='/path/to/working/directory', usePTY=True,
                                      command='true'))

        self.assertEqual(self.step.describe(), ['x'])

        if runtime.platformType == 'win32':
            exp_argv = [r'C:\WINDOWS\system32\cmd.exe', '/c', 'true']
        else:
            exp_argv = ['/bin/sh', '-c', 'true']
        self.patchSpawnProcess(
            exp_cmd=exp_argv[0], exp_argv=exp_argv,
            exp_path='/path/to/working/directory', exp_usePTY=True, exp_env={'a': 'b'},
            outputs=[
                ('out', 'hello!\n'),
                ('err', 'world\n'),
                ('rc', 0),
            ])
        self.expectOutcome(result=SUCCESS, status_text=['y'])
        return self.runStep()

    def test_env_subst(self):
        cmd = [sys.executable, '-c', 'import os; print os.environ["HELLO"]']
        os.environ['WORLD'] = 'hello'
        self.setupStep(
            master.MasterShellCommand(command=cmd,
                                      env={'HELLO': '${WORLD}'}))
        if runtime.platformType == 'win32':
            self.expectLogfile('stdio', "hello\r\n")
        else:
            self.expectLogfile('stdio', "hello\n")
        self.expectOutcome(result=SUCCESS, status_text=["Ran"])

        def _restore_env(res):
            del os.environ['WORLD']
            return res
        d = self.runStep()
        d.addBoth(_restore_env)
        return d

    def test_env_list_subst(self):
        cmd = [sys.executable, '-c', 'import os; print os.environ["HELLO"]']
        os.environ['WORLD'] = 'hello'
        os.environ['LIST'] = 'world'
        self.setupStep(
            master.MasterShellCommand(command=cmd,
                                      env={'HELLO': ['${WORLD}', '${LIST}']}))
        if runtime.platformType == 'win32':
            self.expectLogfile('stdio', "hello;world\r\n")
        else:
            self.expectLogfile('stdio', "hello:world\n")
        self.expectOutcome(result=SUCCESS, status_text=["Ran"])

        def _restore_env(res):
            del os.environ['WORLD']
            del os.environ['LIST']
            return res
        d = self.runStep()
        d.addBoth(_restore_env)
        return d

    def test_prop_rendering(self):
        cmd = [sys.executable, '-c', WithProperties(
            'import os; print "%s"; print os.environ[\"BUILD\"]',
            'project')]
        self.setupStep(
            master.MasterShellCommand(command=cmd,
                                      env={'BUILD': WithProperties('%s', "project")}))
        self.properties.setProperty("project", "BUILDBOT-TEST", "TEST")
        if runtime.platformType == 'win32':
            self.expectLogfile('stdio', "BUILDBOT-TEST\r\nBUILDBOT-TEST\r\n")
        else:
            self.expectLogfile('stdio', "BUILDBOT-TEST\nBUILDBOT-TEST\n")
        self.expectOutcome(result=SUCCESS, status_text=["Ran"])
        return self.runStep()

    def test_path_is_renderable(self):
        """
        The ``path`` argument of ``MasterShellCommand`` is renderable.`
        """
        path = FilePath(self.mktemp())
        path.createDirectory()
        cmd = [sys.executable, '-c', 'import os, sys; sys.stdout.write(os.getcwd())']
        self.setupStep(
            master.MasterShellCommand(command=cmd, path=Interpolate(path.path)))
        self.expectLogfile('stdio', path.path)
        self.expectOutcome(result=SUCCESS, status_text=["Ran"])
        return self.runStep()

    def test_path_absolute(self):
        """
        If the ``path`` argument is absolute, the command is executed in that directory,
        and that directory is logged.
        """
        path = FilePath(self.mktemp())
        path.createDirectory()
        cmd = [sys.executable, '-c', 'import os, sys; sys.stdout.write(os.getcwd())']
        self.setupStep(
            master.MasterShellCommand(command=cmd, path=path.path))
        self.expectLogfile('stdio', path.path)
        self.expectOutcome(result=SUCCESS, status_text=["Ran"])
        d = self.runStep()

        @d.addCallback
        def check(_):
            headers = self.step_status.logs['stdio'].header.splitlines()
            self.assertIn(" in dir %s" % (path.path,), headers)
        return d

    def test_path_relative(self):
        """
        If the ``path`` argument is relative, the path is combined with the
        current working directory. The command is executed in that directory,
        and that directory is logged.
        """
        base_path = FilePath(self.mktemp())
        base_path.createDirectory()
        child_path = base_path.child('child')
        child_path.createDirectory()
        cmd = [sys.executable, '-c', 'import os, sys; sys.stdout.write(os.getcwd())']

        old_cwd = os.getcwd()
        os.chdir(base_path.path)
        self.addCleanup(os.chdir, old_cwd)

        self.setupStep(
            master.MasterShellCommand(command=cmd, path="child"))
        self.expectLogfile('stdio', child_path.path)
        self.expectOutcome(result=SUCCESS, status_text=["Ran"])
        d = self.runStep()

        @d.addCallback
        def check(_):
            headers = self.step_status.logs['stdio'].header.splitlines()
            self.assertIn(" in dir %s" % (child_path.path,), headers)
        return d

    def test_constr_args_descriptionSuffix(self):
        self.setupStep(
            master.MasterShellCommand(description='x', descriptionDone='y',
                                      descriptionSuffix='z',
                                      env={'a': 'b'}, path='/path/to/working/directory', usePTY=True,
                                      command='true'))

        # call twice to make sure the suffix doesn't get double added
        self.assertEqual(self.step.describe(), ['x', 'z'])
        self.assertEqual(self.step.describe(), ['x', 'z'])

        if runtime.platformType == 'win32':
            exp_argv = [r'C:\WINDOWS\system32\cmd.exe', '/c', 'true']
        else:
            exp_argv = ['/bin/sh', '-c', 'true']
        self.patchSpawnProcess(
            exp_cmd=exp_argv[0], exp_argv=exp_argv,
            exp_path='/path/to/working/directory', exp_usePTY=True, exp_env={'a': 'b'},
            outputs=[
                ('out', 'hello!\n'),
                ('err', 'world\n'),
                ('rc', 0),
            ])
        self.expectOutcome(result=SUCCESS, status_text=['y', 'z'])
        return self.runStep()


class TestSetProperty(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_simple(self):
        self.setupStep(master.SetProperty(property="testProperty", value=Interpolate("sch=%(prop:scheduler)s, slave=%(prop:slavename)s")))
        self.properties.setProperty('scheduler', 'force', source='SetProperty', runtime=True)
        self.properties.setProperty('slavename', 'testSlave', source='SetProperty', runtime=True)
        self.expectOutcome(result=SUCCESS, status_text=["Set"])
        self.expectProperty('testProperty', 'sch=force, slave=testSlave', source='SetProperty')
        return self.runStep()


class TestLogRenderable(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
        return self.tearDownBuildStep()

    def test_simple(self):
        self.setupStep(master.LogRenderable(content=Interpolate('sch=%(prop:scheduler)s, slave=%(prop:slavename)s')))
        self.properties.setProperty('scheduler', 'force', source='TestSetProperty', runtime=True)
        self.properties.setProperty('slavename', 'testSlave', source='TestSetProperty', runtime=True)
        self.expectOutcome(result=SUCCESS, status_text=['Logged'])
        self.expectLogfile('Output', pprint.pformat('sch=force, slave=testSlave'))
        return self.runStep()
