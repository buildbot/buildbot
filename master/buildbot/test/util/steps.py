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

import mock
from buildbot.process import buildstep
from buildbot.test.fake import remotecommand


class BuildStepMixin(object):
    """
    Support for testing build steps.  This class adds two capabilities:

     - patch out RemoteCommand with fake versions that check expected
       commands and produce the appropriate results

     - surround a step with the mock objects that it needs to execute

    The following instance variables are available after C{setupStep}:

    @ivar step: the step under test
    @ivar progress: mock progress object
    @ivar buildslave: mock buildslave object
    @ivar step_status: mock StepStatus object
    """

    def setUpBuildStep(self):
        # make an (admittedly global) reference to this test case so that
        # the fakes can call back to us
        remotecommand.FakeRemoteCommand.testcase = self
        self.patch(buildstep, 'RemoteCommand',
                remotecommand.FakeRemoteCommand)
        self.patch(buildstep, 'LoggedRemoteCommand',
                remotecommand.FakeLoggedRemoteCommand)
        self.patch(buildstep, 'RemoteShellCommand',
                remotecommand.FakeRemoteShellCommand)
        self.expected_remote_commands = []

    def tearDownBuildStep(self):
        # delete the reference added in setUp
        del remotecommand.FakeRemoteCommand.testcase

    # utilities

    def setupStep(self, step, slave_version="99.99", slave_env={}):
        """
        Set up C{step} for testing.  This begins by using C{step} as a factory
        to create a I{new} step instance, thereby testing that the the factory
        arguments are handled correctly.  It then creates a comfortable
        environment for the slave to run in, repleate with a fake build and a
        fake slave.

        @param slave_version: slave version to present; defaults to "99.99"

        @param slave_env: environment from the slave at slave startup
        """
        # yes, Virginia, "factory" refers both to the tuple and its first
        # element TODO: fix that up
        factory, args = step.getStepFactory()
        step = self.step = factory(**args)

        # step.build

        b = mock.Mock(name="build")
        b.render = lambda x : x # render is identity
        b.getSlaveCommandVersion = lambda command, oldversion : slave_version
        b.slaveEnvironment = slave_env.copy()
        step.setBuild(b)

        # step.progress

        step.progress = mock.Mock(name="progress")

        # step.buildslave

        step.buildslave = mock.Mock(name="buildslave")

        # step.step_status

        ss = self.step_status = mock.Mock(name="step_status")

        ss.status_text = None
        ss.logs = {}

        def ss_setText(strings):
            ss.status_text = strings
        ss.setText = ss_setText

        ss.getLogs = lambda : ss.logs

        self.step.setStepStatus(ss)

        # step overrides

        def addLog(name):
            l = remotecommand.FakeLogFile(name)
            ss.logs[name] = l
            return l
        step.addLog = addLog

        return step

    def expectCommands(self, *exp):
        """
        Add to the expected remote commands, along with their results.  Each
        argument should be an instance of L{Expect}.
        """
        self.expected_remote_commands.extend(exp)

    def expectOutcome(self, result, status_text):
        """
        Expect the given result (from L{buildbot.status.results}) and status
        text (a list).
        """
        self.exp_outcome = dict(result=result, status_text=status_text)

    def runStep(self):
        """
        Run the step set up with L{setupStep}, and check the results.

        @returns: Deferred
        """
        self.remote = mock.Mock(name="SlaveBuilder(remote)")
        d = self.step.startStep(self.remote)
        def check(result):
            self.assertEqual(self.expected_remote_commands, [],
                             "assert all expected commands were run")
            got_outcome = dict(result=result,
                        status_text=self.step_status.status_text)
            self.assertEqual(got_outcome, self.exp_outcome)
        d.addCallback(check)
        return d

    # callbacks from the running step

    def _remotecommand_run(self, command, step, remote):
        self.assertEqual(step, self.step)
        self.assertEqual(remote, self.remote)
        got = (command.remote_command, command.args)

        if not self.expected_remote_commands:
            self.fail("got command %r when no further commands were expected"
                    % (got,))
        exp = self.expected_remote_commands.pop(0)
        self.assertEqual(got, (exp.remote_command, exp.args))

        # let the Expect object show any behaviors that are required
        return exp.runBehaviors(command)

