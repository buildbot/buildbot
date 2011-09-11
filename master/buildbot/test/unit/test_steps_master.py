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

import sys
import mock
from twisted.internet import reactor
from twisted.trial import unittest
from buildbot.test.util import steps
from buildbot.status.results import SUCCESS, FAILURE
from buildbot.steps import master

class TestMasterShellCommand(steps.BuildStepMixin, unittest.TestCase):

    def setUp(self):
        return self.setUpBuildStep()

    def tearDown(self):
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
                    so = mock.Mock(name='status_object')
                    so.value.exitCode = output[1]
                    pp.processEnded(so)
        self.patch(reactor, 'spawnProcess', spawnProcess)

    def test_real_cmd(self):
        cmd = [ sys.executable, '-c', 'print "hello"' ]
        self.setupStep(
                master.MasterShellCommand(command=cmd))
        self.expectLogfile('stdio', "hello\n")
        self.expectOutcome(result=SUCCESS, status_text=["Ran"])
        return self.runStep()

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
        self.patchSpawnProcess(
                exp_cmd='/bin/sh', exp_argv=['/bin/sh', '-c', 'true'],
                exp_path=['/usr/bin'], exp_usePTY=True, exp_env={'a':'b'},
                outputs=[
                    ('out', 'hello!\n'),
                    ('err', 'world\n'),
                    ('rc', 0),
                ])
        self.expectOutcome(result=SUCCESS, status_text=['y'])
        return self.runStep()
