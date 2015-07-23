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
from __future__ import print_function

import mock

from twisted.python import log

from buildbot import interfaces
from buildbot.process import buildstep
from buildbot.process import remotecommand as real_remotecommand
from buildbot.test.fake import fakebuild
from buildbot.test.fake import fakemaster
from buildbot.test.fake import logfile
from buildbot.test.fake import remotecommand
from buildbot.test.fake import slave
from twisted.internet import defer
from twisted.internet import task


class BuildStepMixin(object):

    """
    Support for testing build steps.  This class adds two capabilities:

     - patch out RemoteCommand with fake versions that check expected
       commands and produce the appropriate results

     - surround a step with the mock objects that it needs to execute

    The following instance variables are available after C{setupStep}:

    @ivar step: the step under test
    @ivar build: the fake build containing the step
    @ivar progress: mock progress object
    @ivar buildslave: mock buildslave object
    @ivar properties: build properties (L{Properties} instance)
    """

    def setUpBuildStep(self):
        # make an (admittedly global) reference to this test case so that
        # the fakes can call back to us
        remotecommand.FakeRemoteCommand.testcase = self
        for module in buildstep, real_remotecommand:
            self.patch(module, 'RemoteCommand',
                       remotecommand.FakeRemoteCommand)
            self.patch(module, 'RemoteShellCommand',
                       remotecommand.FakeRemoteShellCommand)
        self.expected_remote_commands = []

    def tearDownBuildStep(self):
        # delete the reference added in setUp
        del remotecommand.FakeRemoteCommand.testcase

    # utilities

    def setupStep(self, step, slave_version={'*': "99.99"}, slave_env={},
                  buildFiles=[], wantDefaultWorkdir=True, wantData=True,
                  wantDb=False, wantMq=False):
        """
        Set up C{step} for testing.  This begins by using C{step} as a factory
        to create a I{new} step instance, thereby testing that the the factory
        arguments are handled correctly.  It then creates a comfortable
        environment for the slave to run in, replete with a fake build and a
        fake slave.

        As a convenience, it can set the step's workdir with C{'wkdir'}.

        @param slave_version: slave version to present, as a dictionary mapping
            command name to version.  A command name of '*' will apply for all
            commands.

        @param slave_env: environment from the slave at slave startup

        @param wantData(bool): Set to True to add data API connector to master.
            Default value: True.

        @param wantDb(bool): Set to True to add database connector to master.
            Default value: False.

        @param wantMq(bool): Set to True to add mq connector to master.
            Default value: False.
        """
        factory = interfaces.IBuildStepFactory(step)

        step = self.step = factory.buildStep()
        self.master = fakemaster.make_master(wantData=wantData, wantDb=wantDb,
                                             wantMq=wantMq, testcase=self)

        # set defaults
        if wantDefaultWorkdir:
            step.workdir = step._workdir or 'wkdir'

        # step.build

        b = self.build = fakebuild.FakeBuild(master=self.master)
        b.allFiles = lambda: buildFiles
        b.master = self.master

        def getSlaveVersion(cmd, oldversion):
            if cmd in slave_version:
                return slave_version[cmd]
            if '*' in slave_version:
                return slave_version['*']
            return oldversion
        b.getSlaveCommandVersion = getSlaveVersion
        b.slaveEnvironment = slave_env.copy()
        step.setBuild(b)

        # watch for properties being set
        self.properties = interfaces.IProperties(b)

        # step.progress

        step.progress = mock.Mock(name="progress")

        # step.buildslave

        self.buildslave = step.buildslave = slave.FakeSlave(self.master)

        # step overrides

        def addLog(name, type='s', logEncoding=None):
            l = logfile.FakeLogFile(name, step)
            self.step.logs[name] = l
            return defer.succeed(l)
        step.addLog = addLog
        step.addLog_newStyle = addLog

        def addHTMLLog(name, html):
            l = logfile.FakeLogFile(name, step)
            l.addStdout(html)
            return defer.succeed(None)
        step.addHTMLLog = addHTMLLog

        def addCompleteLog(name, text):
            l = logfile.FakeLogFile(name, step)
            self.step.logs[name] = l
            l.addStdout(text)
            return defer.succeed(None)
        step.addCompleteLog = addCompleteLog

        step.logobservers = self.logobservers = {}

        def addLogObserver(logname, observer):
            self.logobservers.setdefault(logname, []).append(observer)
            observer.step = step
        step.addLogObserver = addLogObserver

        # add any observers defined in the constructor, before this
        # monkey-patch
        for n, o in step._pendingLogObservers:
            addLogObserver(n, o)

        # expectations

        self.exp_result = None
        self.exp_state_string = None
        self.exp_properties = {}
        self.exp_missing_properties = []
        self.exp_logfiles = {}
        self.exp_hidden = False

        # check that the step's name is not None
        self.assertNotEqual(step.name, None)

        # mock out the reactor for updateSummary's debouncing
        self.debounceClock = task.Clock()
        step.updateSummary._reactor = self.debounceClock

        return step

    def expectCommands(self, *exp):
        """
        Add to the expected remote commands, along with their results.  Each
        argument should be an instance of L{Expect}.
        """
        self.expected_remote_commands.extend(exp)

    def expectOutcome(self, result, state_string=None):
        """
        Expect the given result (from L{buildbot.status.results}) and status
        text (a list).
        """
        self.exp_result = result
        if state_string:
            self.exp_state_string = state_string

    def expectProperty(self, property, value, source=None):
        """
        Expect the given property to be set when the step is complete.
        """
        self.exp_properties[property] = (value, source)

    def expectNoProperty(self, property):
        """
        Expect the given property is *not* set when the step is complete
        """
        self.exp_missing_properties.append(property)

    def expectLogfile(self, logfile, contents):
        """
        Expect a logfile with the given contents
        """
        self.exp_logfiles[logfile] = contents

    def expectHidden(self, hidden):
        """
        Set whether the step is expected to be hidden.
        """
        self.exp_hidden = hidden

    def runStep(self):
        """
        Run the step set up with L{setupStep}, and check the results.

        @returns: Deferred
        """
        self.conn = mock.Mock(name="SlaveBuilder(connection)")
        self.step.setupProgress()
        d = self.step.startStep(self.conn)

        @d.addCallback
        def check(result):
            # finish up the debounced updateSummary before checking
            self.debounceClock.advance(1)
            self.assertEqual(self.expected_remote_commands, [],
                             "assert all expected commands were run")

            # in case of unexpected result, display logs in stdout for debugging failing tests
            if result != self.exp_result:
                for loog in self.step.logs.values():
                    print(loog.stdout)
                    print(loog.stderr)

            self.assertEqual(result, self.exp_result, "expected result")
            if self.exp_state_string:
                stepStateString = self.master.data.updates.stepStateString
                stepids = stepStateString.keys()
                assert stepids, "no step state strings were set"
                self.assertEqual(stepStateString[stepids[0]],
                                 self.exp_state_string,
                                 "expected step state strings")
            for pn, (pv, ps) in self.exp_properties.iteritems():
                self.assertTrue(self.properties.hasProperty(pn),
                                "missing property '%s'" % pn)
                self.assertEqual(self.properties.getProperty(pn),
                                 pv, "property '%s'" % pn)
                if ps is not None:
                    self.assertEqual(
                        self.properties.getPropertySource(pn), ps, "property '%s' source" % pn)
            for pn in self.exp_missing_properties:
                self.assertFalse(self.properties.hasProperty(pn),
                                 "unexpected property '%s'" % pn)
            for l, contents in self.exp_logfiles.iteritems():
                self.assertEqual(
                    self.step.logs[l].stdout, contents, "log '%s' contents" % l)
            # XXX TODO: hidden
            # self.step_status.setHidden.assert_called_once_with(self.exp_hidden)
        return d

    # callbacks from the running step

    def _remotecommand_run(self, command, step, conn, builder_name):
        self.assertEqual(step, self.step)
        self.assertEqual(conn, self.conn)
        got = (command.remote_command, command.args)

        if not self.expected_remote_commands:
            self.fail("got command %r when no further commands were expected"
                      % (got,))

        exp = self.expected_remote_commands.pop(0)

        # handle any incomparable args
        for arg in exp.incomparable_args:
            self.failUnless(arg in got[1],
                            "incomparable arg '%s' not received" % (arg,))
            del got[1][arg]

        # first check any ExpectedRemoteReference instances
        try:
            self.assertEqual((exp.remote_command, exp.args), got)
        except AssertionError:
            # log this error, as the step may swallow the AssertionError or
            # otherwise obscure the failure.  Trial will see the exception in
            # the log and print an [ERROR].  This may result in
            # double-reporting, but that's better than non-reporting!
            log.err()
            raise

        # let the Expect object show any behaviors that are required
        d = exp.runBehaviors(command)
        d.addCallback(lambda _: command)
        return d
