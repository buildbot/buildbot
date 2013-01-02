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
import sys
from twisted.python import failure, runtime
from twisted.internet import error, reactor
from twisted.trial import unittest
from buildbot.test.util import steps
from buildbot.status.results import SUCCESS, FAILURE, EXCEPTION
from buildbot.steps import master
from buildbot.process.properties import WithProperties

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
        cmd = [ sys.executable, '-c', 'print "hello"' ]
        self.setupStep(
                master.MasterShellCommand(command=cmd))
        if runtime.platformType == 'win32':
            self.expectLogfile('stdio', "hello\r\n")
        else:
            self.expectLogfile('stdio', "hello\n")
        self.expectOutcome(result=SUCCESS, status_text=["Ran"])
        return self.runStep()

    def test_real_cmd_interrupted(self):
        cmd = [ sys.executable, '-c', 'while True: pass' ]
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
        cmd = [ sys.executable, '-c', 'import sys; sys.exit(1)' ]
        self.setupStep(
                master.MasterShellCommand(command=cmd))
        self.expectLogfile('stdio', "")
        self.expectOutcome(result=FAILURE, status_text=["failed (1)"])
        return self.runStep()

    def test_constr_args(self):
        self.setupStep(
                master.MasterShellCommand(description='x', descriptionDone='y',
                                env={'a':'b'}, path=['/usr/bin'], usePTY=True,
                                command='true'))

        self.assertEqual(self.step.describe(), ['x'])

        if runtime.platformType == 'win32':
            exp_argv = [ r'C:\WINDOWS\system32\cmd.exe', '/c', 'true' ]
        else:
            exp_argv = [ '/bin/sh', '-c', 'true' ]
        self.patchSpawnProcess(
                exp_cmd=exp_argv[0], exp_argv=exp_argv,
                exp_path=['/usr/bin'], exp_usePTY=True, exp_env={'a':'b'},
                outputs=[
                    ('out', 'hello!\n'),
                    ('err', 'world\n'),
                    ('rc', 0),
                ])
        self.expectOutcome(result=SUCCESS, status_text=['y'])
        return self.runStep()

    def test_env_subst(self):
        cmd = [ sys.executable, '-c', 'import os; print os.environ["HELLO"]' ]
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
        cmd = [ sys.executable, '-c', 'import os; print os.environ["HELLO"]' ]
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
        cmd = [ sys.executable, '-c', WithProperties(
                    'import os; print "%s"; print os.environ[\"BUILD\"]',
                    'project') ]
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

    def test_constr_args_descriptionSuffix(self):
        self.setupStep(
                master.MasterShellCommand(description='x', descriptionDone='y',
                                          descriptionSuffix='z',
                                env={'a':'b'}, path=['/usr/bin'], usePTY=True,
                                command='true'))

        # call twice to make sure the suffix doesnt get double added
        self.assertEqual(self.step.describe(), ['x', 'z'])
        self.assertEqual(self.step.describe(), ['x', 'z'])

        if runtime.platformType == 'win32':
            exp_argv = [ r'C:\WINDOWS\system32\cmd.exe', '/c', 'true' ]
        else:
            exp_argv = [ '/bin/sh', '-c', 'true' ]
        self.patchSpawnProcess(
                exp_cmd=exp_argv[0], exp_argv=exp_argv,
                exp_path=['/usr/bin'], exp_usePTY=True, exp_env={'a':'b'},
                outputs=[
                    ('out', 'hello!\n'),
                    ('err', 'world\n'),
                    ('rc', 0),
                ])
        self.expectOutcome(result=SUCCESS, status_text=['y', 'z'])
        return self.runStep()
