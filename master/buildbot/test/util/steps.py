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
from __future__ import division
from __future__ import print_function
from future.utils import iteritems
from future.utils import itervalues

import mock

from twisted.internet import defer
from twisted.internet import task
from twisted.python import log

from buildbot import interfaces
from buildbot.process import remotecommand as real_remotecommand
from buildbot.process import buildstep
from buildbot.process.results import EXCEPTION
from buildbot.test.fake import fakebuild
from buildbot.test.fake import fakemaster
from buildbot.test.fake import logfile
from buildbot.test.fake import remotecommand
from buildbot.test.fake import worker
from buildbot.util import bytes2NativeString


def _dict_diff(d1, d2):
    """
    Given two dictionaries describe their difference
    For nested dictionaries, key-paths are concatenated with the '.' operator

    @return The list of keys missing in d1, the list of keys missing in d2, and the differences
    in any nested keys
    """
    d1_keys = set(d1.keys())
    d2_keys = set(d2.keys())
    both = d1_keys & d2_keys

    missing_in_d1 = []
    missing_in_d2 = []
    different = []

    for k in both:
        if isinstance(d1[k], dict) and isinstance(d2[k], dict):
            missing_in_v1, missing_in_v2, different_in_v = _dict_diff(
                d1[k], d2[k])
            missing_in_d1.extend(['{0}.{1}'.format(k, m)
                                  for m in missing_in_v1])
            missing_in_d2.extend(['{0}.{1}'.format(k, m)
                                  for m in missing_in_v2])
            for child_k, left, right in different_in_v:
                different.append(('{0}.{1}'.format(k, child_k), left, right))
            continue
        if d1[k] != d2[k]:
            different.append((k, d1[k], d2[k]))
    missing_in_d1.extend(d2_keys - both)
    missing_in_d2.extend(d1_keys - both)
    return missing_in_d1, missing_in_d2, different


def _describe_cmd_difference(exp, command):
    if exp.args == command.args:
        return

    missing_in_exp, missing_in_cmd, diff = _dict_diff(exp.args, command.args)
    if missing_in_exp:
        log.msg(
            'Keys in cmd missing from expectation: {0}'.format(missing_in_exp))
    if missing_in_cmd:
        log.msg(
            'Keys in expectation missing from command: {0}'.format(missing_in_cmd))
    if diff:
        formatted_diff = [
            '"{0}": expected {1!r}, got {2!r}'.format(*d) for d in diff]
        log.msg('Key differences between expectation and command: {0}'.format(
            '\n'.join(formatted_diff)))


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
    @ivar worker: mock worker object
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
    def _getWorkerCommandVersionWrapper(self):
        originalGetWorkerCommandVersion = self.step.build.getWorkerCommandVersion

        def getWorkerCommandVersion(cmd, oldversion):
            return originalGetWorkerCommandVersion(cmd, oldversion)

        return getWorkerCommandVersion

    def setupStep(self, step, worker_version=None, worker_env=None,
                  buildFiles=None, wantDefaultWorkdir=True, wantData=True,
                  wantDb=False, wantMq=False):
        """
        Set up C{step} for testing.  This begins by using C{step} as a factory
        to create a I{new} step instance, thereby testing that the factory
        arguments are handled correctly.  It then creates a comfortable
        environment for the worker to run in, replete with a fake build and a
        fake worker.

        As a convenience, it can set the step's workdir with C{'wkdir'}.

        @param worker_version: worker version to present, as a dictionary mapping
            command name to version.  A command name of '*' will apply for all
            commands.

        @param worker_env: environment from the worker at worker startup

        @param wantData(bool): Set to True to add data API connector to master.
            Default value: True.

        @param wantDb(bool): Set to True to add database connector to master.
            Default value: False.

        @param wantMq(bool): Set to True to add mq connector to master.
            Default value: False.
        """
        if worker_version is None:
            worker_version = {
                '*': '99.99'
            }

        if worker_env is None:
            worker_env = dict()

        if buildFiles is None:
            buildFiles = list()

        factory = interfaces.IBuildStepFactory(step)

        step = self.step = factory.buildStep()
        self.master = fakemaster.make_master(wantData=wantData, wantDb=wantDb,
                                             wantMq=wantMq, testcase=self)

        # mock out the reactor for updateSummary's debouncing
        self.debounceClock = task.Clock()
        self.master.reactor = self.debounceClock

        # set defaults
        if wantDefaultWorkdir:
            step.workdir = step._workdir or 'wkdir'

        # step.build

        b = self.build = fakebuild.FakeBuild(master=self.master)
        b.allFiles = lambda: buildFiles
        b.master = self.master

        def getWorkerVersion(cmd, oldversion):
            if cmd in worker_version:
                return worker_version[cmd]
            if '*' in worker_version:
                return worker_version['*']
            return oldversion
        b.getWorkerCommandVersion = getWorkerVersion
        b.workerEnvironment = worker_env.copy()
        step.setBuild(b)

        # watch for properties being set
        self.properties = interfaces.IProperties(b)

        # step.progress

        step.progress = mock.Mock(name="progress")

        # step.worker

        self.worker = step.worker = worker.FakeWorker(self.master)

        # step overrides

        def addLog(name, type='s', logEncoding=None):
            _log = logfile.FakeLogFile(name, step)
            self.step.logs[name] = _log
            return defer.succeed(_log)
        step.addLog = addLog
        step.addLog_newStyle = addLog

        def addHTMLLog(name, html):
            _log = logfile.FakeLogFile(name, step)
            html = bytes2NativeString(html)
            _log.addStdout(html)
            return defer.succeed(None)
        step.addHTMLLog = addHTMLLog

        def addCompleteLog(name, text):
            _log = logfile.FakeLogFile(name, step)
            self.step.logs[name] = _log
            _log.addStdout(text)
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
        self.exp_exception = None

        # check that the step's name is not None
        self.assertNotEqual(step.name, None)

        return step

    def expectCommands(self, *exp):
        """
        Add to the expected remote commands, along with their results.  Each
        argument should be an instance of L{Expect}.
        """
        self.expected_remote_commands.extend(exp)

    def expectOutcome(self, result, state_string=None):
        """
        Expect the given result (from L{buildbot.process.results}) and status
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

    def expectException(self, exception_class):
        """
        Set whether the step is expected to raise an exception.
        """
        self.exp_exception = exception_class
        self.expectOutcome(EXCEPTION)

    def runStep(self):
        """
        Run the step set up with L{setupStep}, and check the results.

        @returns: Deferred
        """
        self.step.build.getWorkerCommandVersion = self._getWorkerCommandVersionWrapper()

        self.conn = mock.Mock(name="WorkerForBuilder(connection)")
        self.step.setupProgress()
        d = self.step.startStep(self.conn)

        @d.addCallback
        def check(result):
            # finish up the debounced updateSummary before checking
            self.debounceClock.advance(1)
            if self.expected_remote_commands:
                log.msg("un-executed remote commands:")
                for rc in self.expected_remote_commands:
                    log.msg(repr(rc))
                raise AssertionError("un-executed remote commands; see logs")

            # in case of unexpected result, display logs in stdout for
            # debugging failing tests
            if result != self.exp_result:
                log.msg("unexpected result from step; dumping logs")
                for l in itervalues(self.step.logs):
                    if l.stdout:
                        log.msg("{0} stdout:\n{1}".format(l.name, l.stdout))
                    if l.stderr:
                        log.msg("{0} stderr:\n{1}".format(l.name, l.stderr))
                raise AssertionError("unexpected result; see logs")

            if self.exp_state_string:
                stepStateString = self.master.data.updates.stepStateString
                stepids = list(stepStateString)
                assert stepids, "no step state strings were set"
                self.assertEqual(
                    self.exp_state_string,
                    stepStateString[stepids[0]],
                    "expected state_string {0!r}, got {1!r}".format(
                        self.exp_state_string,
                        stepStateString[stepids[0]]))
            for pn, (pv, ps) in iteritems(self.exp_properties):
                self.assertTrue(self.properties.hasProperty(pn),
                                "missing property '%s'" % pn)
                self.assertEqual(self.properties.getProperty(pn),
                                 pv, "property '%s'" % pn)
                if ps is not None:
                    self.assertEqual(
                        self.properties.getPropertySource(pn), ps,
                        "property {0!r} source has source {1!r}".format(
                            pn, self.properties.getPropertySource(pn)))
            for pn in self.exp_missing_properties:
                self.assertFalse(self.properties.hasProperty(pn),
                                 "unexpected property '%s'" % pn)
            for l, exp in iteritems(self.exp_logfiles):
                got = self.step.logs[l].stdout
                if got != exp:
                    log.msg("Unexpected log output:\n" + got)
                    raise AssertionError("Unexpected log output; see logs")
            if self.exp_exception:
                self.assertEqual(len(self.flushLoggedErrors(self.exp_exception)), 1)

            # XXX TODO: hidden
            # self.step_status.setHidden.assert_called_once_with(self.exp_hidden)
        return d

    # callbacks from the running step

    @defer.inlineCallbacks
    def _validate_expectation(self, exp, command):
        got = (command.remote_command, command.args)

        for child_exp in exp.nestedExpectations():
            try:
                yield self._validate_expectation(child_exp, command)
                exp.expectationPassed(exp)
            except AssertionError as e:
                # log this error, as the step may swallow the AssertionError or
                # otherwise obscure the failure.  Trial will see the exception in
                # the log and print an [ERROR].  This may result in
                # double-reporting, but that's better than non-reporting!
                log.err()
                exp.raiseExpectationFailure(child_exp, e)

        if exp.shouldAssertCommandEqualExpectation():
            # handle any incomparable args
            for arg in exp.incomparable_args:
                self.assertTrue(arg in got[1],
                                "incomparable arg '%s' not received" % (arg,))
                del got[1][arg]

            # first check any ExpectedRemoteReference instances
            exp_tup = (exp.remote_command, exp.args)
            if exp_tup != got:
                _describe_cmd_difference(exp, command)
                raise AssertionError(
                    "Command contents different from expected; see logs")

        if exp.shouldRunBehaviors():
            # let the Expect object show any behaviors that are required
            yield exp.runBehaviors(command)

    @defer.inlineCallbacks
    def _remotecommand_run(self, command, step, conn, builder_name):
        self.assertEqual(step, self.step)
        self.assertEqual(conn, self.conn)
        got = (command.remote_command, command.args)

        if not self.expected_remote_commands:
            self.fail("got command %r when no further commands were expected"
                      % (got,))

        exp = self.expected_remote_commands[0]
        try:
            yield self._validate_expectation(exp, command)
            exp.expectationPassed(exp)
        except AssertionError as e:
            # log this error, as the step may swallow the AssertionError or
            # otherwise obscure the failure.  Trial will see the exception in
            # the log and print an [ERROR].  This may result in
            # double-reporting, but that's better than non-reporting!
            log.err()
            exp.raiseExpectationFailure(exp, e)
        finally:
            if not exp.shouldKeepMatchingAfter(command):
                self.expected_remote_commands.pop(0)
        defer.returnValue(command)
