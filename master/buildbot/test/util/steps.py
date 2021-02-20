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

from twisted.internet import defer
from twisted.python import log
from twisted.python.reflect import namedModule

from buildbot.process import buildstep
from buildbot.process import remotecommand as real_remotecommand
from buildbot.process.results import EXCEPTION
from buildbot.test.fake import fakebuild
from buildbot.test.fake import fakemaster
from buildbot.test.fake import logfile
from buildbot.test.fake import remotecommand
from buildbot.test.fake import worker
from buildbot.util import bytes2unicode


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


def _describe_cmd_difference(exp_command, exp_args, got_command, got_args):
    if exp_command != got_command:
        return 'Expected command type {} got {}. Expected args {}'.format(exp_command, got_command,
                                                                          repr(exp_args))
    if exp_args == got_args:
        return ""
    text = ""
    missing_in_exp, missing_in_cmd, diff = _dict_diff(exp_args, got_args)
    if missing_in_exp:
        missing_dict = {key: got_args[key] for key in missing_in_exp}
        text += 'Keys in cmd missing from expectation: {0!r}\n'.format(missing_dict)
    if missing_in_cmd:
        missing_dict = {key: exp_args[key] for key in missing_in_cmd}
        text += 'Keys in expectation missing from command: {0!r}\n'.format(missing_dict)
    if diff:
        formatted_diff = [
            '"{0}": expected {1!r}, got {2!r}'.format(*d) for d in diff]
        text += ('Key differences between expectation and command: {0}\n'.format(
            '\n'.join(formatted_diff)))
    return text


class BuildStepMixin:

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

    def setUpBuildStep(self, wantData=True, wantDb=False, wantMq=False):
        """
        @param wantData(bool): Set to True to add data API connector to master.
            Default value: True.

        @param wantDb(bool): Set to True to add database connector to master.
            Default value: False.

        @param wantMq(bool): Set to True to add mq connector to master.
            Default value: False.
        """

        if not hasattr(self, 'reactor'):
            raise Exception('Reactor has not yet been setup for step')

        self._next_remote_command_number = 0
        self._interrupt_remote_command_numbers = []

        def create_fake_remote_command(*args, **kwargs):
            cmd = remotecommand.FakeRemoteCommand(*args, **kwargs)
            cmd.testcase = self
            if self._next_remote_command_number in self._interrupt_remote_command_numbers:
                cmd.set_run_interrupt()
            self._next_remote_command_number += 1
            return cmd

        def create_fake_remote_shell_command(*args, **kwargs):
            cmd = remotecommand.FakeRemoteShellCommand(*args, **kwargs)
            cmd.testcase = self
            if self._next_remote_command_number in self._interrupt_remote_command_numbers:
                cmd.set_run_interrupt()
            self._next_remote_command_number += 1
            return cmd

        self.patch(real_remotecommand, 'RemoteCommand', create_fake_remote_command)
        self.patch(real_remotecommand, 'RemoteShellCommand', create_fake_remote_shell_command)
        self.expected_remote_commands = []
        self._expected_remote_commands_popped = 0

        self.master = fakemaster.make_master(self, wantData=wantData, wantDb=wantDb, wantMq=wantMq)

    def tearDownBuildStep(self):
        pass

    def setupStep(self, step, worker_version=None, worker_env=None,
                  buildFiles=None, wantDefaultWorkdir=True):
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
        """
        if worker_version is None:
            worker_version = {
                '*': '99.99'
            }

        if worker_env is None:
            worker_env = dict()

        if buildFiles is None:
            buildFiles = list()

        step = self.step = buildstep.create_step_from_step_or_factory(step)

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

        self.build.builder.config.env = worker_env.copy()

        # watch for properties being set
        self.properties = b.getProperties()

        # step.progress

        step.progress = mock.Mock(name="progress")

        # step.worker

        self.worker = step.worker = worker.FakeWorker(self.master)
        self.worker.attached(None)

        # step overrides

        def addLog(name, type='s', logEncoding=None):
            _log = logfile.FakeLogFile(name)
            self.step.logs[name] = _log
            self.step._connectPendingLogObservers()
            return defer.succeed(_log)
        step.addLog = addLog
        step.addLog_newStyle = addLog

        def addHTMLLog(name, html):
            _log = logfile.FakeLogFile(name)
            html = bytes2unicode(html)
            _log.addStdout(html)
            return defer.succeed(None)
        step.addHTMLLog = addHTMLLog

        def addCompleteLog(name, text):
            _log = logfile.FakeLogFile(name)
            if name in self.step.logs:
                raise Exception('Attempt to add log {} twice to the logs'.format(name))
            self.step.logs[name] = _log
            _log.addStdout(text)
            return defer.succeed(None)
        step.addCompleteLog = addCompleteLog

        self._got_test_result_sets = []
        self._next_test_result_set_id = 1000

        def add_test_result_set(description, category, value_unit):
            self._got_test_result_sets.append((description, category, value_unit))

            setid = self._next_test_result_set_id
            self._next_test_result_set_id += 1
            return defer.succeed(setid)

        step.addTestResultSet = add_test_result_set

        self._got_test_results = []

        def add_test_result(setid, value, test_name=None, test_code_path=None, line=None,
                            duration_ns=None):
            self._got_test_results.append((setid, value, test_name, test_code_path, line,
                                           duration_ns))
        step.addTestResult = add_test_result

        # expectations

        self.exp_result = None
        self.exp_state_string = None
        self.exp_properties = {}
        self.exp_missing_properties = []
        self.exp_logfiles = {}
        self.exp_hidden = False
        self.exp_exception = None
        self._exp_test_result_sets = []
        self._exp_test_results = []

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

    def expectTestResultSets(self, sets):
        self._exp_test_result_sets = sets

    def expectTestResults(self, results):
        self._exp_test_results = results

    def _dump_logs(self):
        for l in self.step.logs.values():
            if l.stdout:
                log.msg("{0} stdout:\n{1}".format(l.name, l.stdout))
            if l.stderr:
                log.msg("{0} stderr:\n{1}".format(l.name, l.stderr))

    @defer.inlineCallbacks
    def runStep(self):
        """
        Run the step set up with L{setupStep}, and check the results.

        @returns: Deferred
        """
        self.conn = mock.Mock(name="WorkerForBuilder(connection)")
        self.step.setupProgress()
        result = yield self.step.startStep(self.conn)

        # finish up the debounced updateSummary before checking
        self.reactor.advance(1)
        if self.expected_remote_commands:
            log.msg("un-executed remote commands:")
            for rc in self.expected_remote_commands:
                log.msg(repr(rc))
            raise AssertionError("un-executed remote commands; see logs")

        # in case of unexpected result, display logs in stdout for
        # debugging failing tests
        if result != self.exp_result:
            msg = "unexpected result from step; expected {}, got {}".format(self.exp_result, result)
            log.msg("{}; dumping logs".format(msg))
            self._dump_logs()
            raise AssertionError("{}; see logs".format(msg))

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
        for pn, (pv, ps) in self.exp_properties.items():
            self.assertTrue(self.properties.hasProperty(pn), "missing property '{}'".format(pn))
            self.assertEqual(self.properties.getProperty(pn), pv, "property '{}'".format(pn))
            if ps is not None:
                self.assertEqual(
                    self.properties.getPropertySource(pn), ps,
                    "property {0!r} source has source {1!r}".format(
                        pn, self.properties.getPropertySource(pn)))
        for pn in self.exp_missing_properties:
            self.assertFalse(self.properties.hasProperty(pn), "unexpected property '{}'".format(pn))
        for l, exp in self.exp_logfiles.items():
            got = self.step.logs[l].stdout
            if got != exp:
                log.msg("Unexpected log output:\n" + got)
                log.msg("Expected log output:\n" + exp)
                raise AssertionError("Unexpected log output; see logs")
        if self.exp_exception:
            self.assertEqual(
                len(self.flushLoggedErrors(self.exp_exception)), 1)

        self.assertEqual(self._exp_test_result_sets, self._got_test_result_sets)
        self.assertEqual(self._exp_test_results, self._got_test_results)

        # XXX TODO: hidden
        # self.step_status.setHidden.assert_called_once_with(self.exp_hidden)

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
            self.assertEqual(exp.interrupted, command.interrupted)

            # first check any ExpectedRemoteReference instances
            exp_tup = (exp.remote_command, exp.args)
            if exp_tup != got:
                msg = "Command contents different from expected (command index: {}); {}".format(
                    self._expected_remote_commands_popped,
                    _describe_cmd_difference(exp.remote_command, exp.args,
                                             command.remote_command, command.args))
                raise AssertionError(msg)

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
                self._expected_remote_commands_popped += 1
        return command

    def changeWorkerSystem(self, system):
        self.worker.worker_system = system
        if system in ['nt', 'win32']:
            self.build.path_module = namedModule('ntpath')
            self.worker.worker_basedir = '\\wrk'
        else:
            self.build.path_module = namedModule('posixpath')
            self.worker.worker_basedir = '/wrk'

    def interrupt_nth_remote_command(self, number):
        self._interrupt_remote_command_numbers.append(number)
