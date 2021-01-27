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

import traceback
from io import StringIO

from twisted.internet import defer
from twisted.internet import error
from twisted.python import failure

from buildbot.config import BuilderConfig
from buildbot.process import buildstep
from buildbot.process import logobserver
from buildbot.process import results
from buildbot.process.factory import BuildFactory
from buildbot.steps import shell
from buildbot.test.util.integration import RunFakeMasterTestCase
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.warnings import DeprecatedApiWarning


class TestLogObserver(logobserver.LogObserver):

    def __init__(self):
        self.observed = []

    def outReceived(self, txt):
        self.observed.append(txt)


class OldStyleCustomBuildStep(buildstep.BuildStep):

    def __init__(self, reactor, arg1, arg2, doFail=False, **kwargs):
        super().__init__(**kwargs)
        self.reactor = reactor
        self.arg1 = arg1
        self.arg2 = arg2
        self.doFail = doFail

    def start(self):
        # don't complete immediately, or synchronously
        self.reactor.callLater(0, self.doStuff)

    def doStuff(self):
        try:
            self.addURL('bookmark', 'http://foo')
            self.addHTMLLog('compl.html',
                            "<blink>A very short logfile</blink>\n")

            self.step_status.setText(['text'])
            self.step_status.setText2(['text2'])
            self.step_status.setText(['text3'])

            lo = TestLogObserver()
            self.addLogObserver('foo', lo)

            _log = self.addLog('foo')
            _log.addStdout('stdout\n')
            _log.addStdout('\N{SNOWMAN}\n'.encode('utf-8'))
            _log.addStderr('stderr\n')
            _log.finish()

            self.addCompleteLog('obs', 'Observer saw %r' % (lo.observed,))

            if self.doFail:
                self.failed(failure.Failure(RuntimeError('oh noes')))
            else:
                self.finished(results.SUCCESS)
        except Exception:
            traceback.print_exc()
            self.failed(failure.Failure())


class Latin1ProducingCustomBuildStep(buildstep.BuildStep):

    @defer.inlineCallbacks
    def run(self):
        _log = yield self.addLog('xx')
        output_str = '\N{CENT SIGN}'
        yield _log.addStdout(output_str)
        yield _log.finish()
        return results.SUCCESS


class BuildStepWithFailingLogObserver(buildstep.BuildStep):

    @defer.inlineCallbacks
    def run(self):
        self.addLogObserver('xx', logobserver.LineConsumerLogObserver(self.log_consumer))

        _log = yield self.addLog('xx')
        yield _log.addStdout('line1\nline2\n')
        yield _log.finish()

        return results.SUCCESS

    def log_consumer(self):
        _, _ = yield
        raise RuntimeError('fail')


class FailingCustomStep(buildstep.LoggingBuildStep):

    flunkOnFailure = True

    def __init__(self, exception=buildstep.BuildStepFailed, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.exception = exception

    @defer.inlineCallbacks
    def start(self):
        yield defer.succeed(None)
        raise self.exception()


class OldBuildEPYDoc(shell.ShellCommand):

    command = ['epydoc']

    def runCommand(self, cmd):
        # we don't have a real worker in this test harness, so fake it
        _log = cmd.logs['stdio']
        _log.addStdout('some\noutput\n')
        return defer.succeed(None)

    def createSummary(self, log):
        for line in StringIO(log.getText()):
            # what we do with the line isn't important to the test
            assert line in ('some\n', 'output\n')


class OldPerlModuleTest(shell.ShellCommand):

    command = ['perl']

    def runCommand(self, cmd):
        # we don't have a real worker in this test harness, so fake it
        _log = cmd.logs['stdio']
        _log.addStdout('a\nb\nc\n')
        return defer.succeed(None)

    def evaluateCommand(self, cmd):
        # Get stdio, stripping pesky newlines etc.
        lines = [
            line.replace('\r\n', '').replace('\r', '').replace('\n', '')
            for line in self.getLog('stdio').readlines()
        ]
        # .. the rest of this method isn't that interesting, as long as the
        # statement above worked
        assert lines == ['a', 'b', 'c']
        return results.SUCCESS


class RunSteps(RunFakeMasterTestCase):

    @defer.inlineCallbacks
    def create_config_for_step(self, step):
        config_dict = {
            'builders': [
                BuilderConfig(name="builder",
                              workernames=["worker1"],
                              factory=BuildFactory([step])
                              ),
            ],
            'workers': [self.createLocalWorker('worker1')],
            'protocols': {'null': {}},
            # Disable checks about missing scheduler.
            'multiMaster': True,
        }

        yield self.setup_master(config_dict)
        builder_id = yield self.master.data.updates.findBuilderId('builder')
        return builder_id

    @defer.inlineCallbacks
    def do_test_build(self, builder_id):

        # setup waiting for build to finish
        d_finished = defer.Deferred()

        def on_finished(_, __):
            if not d_finished.called:
                d_finished.callback(None)
        consumer = yield self.master.mq.startConsuming(on_finished, ('builds', None, 'finished'))

        # start the builder
        yield self.create_build_request([builder_id])

        # and wait for build completion
        yield d_finished
        yield consumer.stopConsuming()

    @defer.inlineCallbacks
    def doOldStyleCustomBuildStep(self, builder_id, slowDB=False):
        # patch out addLog to delay until we're ready
        newLogDeferreds = []
        oldNewLog = self.master.data.updates.addLog

        def finishNewLog(self):
            for d in newLogDeferreds:
                self.reactor.callLater(0, d.callback, None)

        def delayedNewLog(*args, **kwargs):
            d = defer.Deferred()
            d.addCallback(lambda _: oldNewLog(*args, **kwargs))
            newLogDeferreds.append(d)
            return d
        if slowDB:
            self.patch(self.master.data.updates,
                       "addLog", delayedNewLog)
            self.patch(OldStyleCustomBuildStep,
                       "_run_finished_hook", finishNewLog)

        yield self.do_test_build(builder_id)

        yield self.assertLogs(1, {
            'compl.html': '<blink>A very short logfile</blink>\n',
            # this is one of the things that differs independently of
            # new/old style: encoding of logs and newlines
            'foo':
            # 'stdout\n\xe2\x98\x83\nstderr\n',
            'ostdout\no\N{SNOWMAN}\nestderr\n',
            'obs':
            # if slowDB, the observer won't see anything before the end of this
            # instant step
            'Observer saw []\n' if slowDB else
            # 'Observer saw [\'stdout\\n\', \'\\xe2\\x98\\x83\\n\']',
            'Observer saw [' + repr('stdout\n') + ", " + repr("\u2603\n") + "]\n"
        })

    @defer.inlineCallbacks
    def test_OldStyleCustomBuildStep(self):
        step = OldStyleCustomBuildStep(self.reactor, arg1=1, arg2=2)
        builder_id = yield self.create_config_for_step(step)
        yield self.doOldStyleCustomBuildStep(builder_id, False)

    @defer.inlineCallbacks
    def test_OldStyleCustomBuildStepSlowDB(self):
        step = OldStyleCustomBuildStep(self.reactor, arg1=1, arg2=2)
        builder_id = yield self.create_config_for_step(step)
        yield self.doOldStyleCustomBuildStep(builder_id, True)

    @defer.inlineCallbacks
    def test_OldStyleCustomBuildStep_failure(self):
        step = OldStyleCustomBuildStep(self.reactor, arg1=1, arg2=2, doFail=1)
        builder_id = yield self.create_config_for_step(step)

        yield self.do_test_build(builder_id)

        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        yield self.assertBuildResults(1, results.EXCEPTION)

    @defer.inlineCallbacks
    def test_step_raising_buildstepfailed_in_start(self):
        builder_id = yield self.create_config_for_step(FailingCustomStep())

        yield self.do_test_build(builder_id)
        yield self.assertBuildResults(1, results.FAILURE)

    @defer.inlineCallbacks
    def test_step_raising_exception_in_start(self):
        builder_id = yield self.create_config_for_step(FailingCustomStep(exception=ValueError))

        yield self.do_test_build(builder_id)
        yield self.assertBuildResults(1, results.EXCEPTION)
        self.assertEqual(len(self.flushLoggedErrors(ValueError)), 1)

    @defer.inlineCallbacks
    def test_step_raising_connectionlost_in_start(self):
        ''' Check whether we can recover from raising ConnectionLost from a step if the worker
            did not actually disconnect
        '''
        step = FailingCustomStep(exception=error.ConnectionLost)
        builder_id = yield self.create_config_for_step(step)

        yield self.do_test_build(builder_id)
        yield self.assertBuildResults(1, results.EXCEPTION)
    test_step_raising_connectionlost_in_start.skip = "Results in infinite loop"

    @defer.inlineCallbacks
    def test_step_raising_in_log_observer(self):
        step = BuildStepWithFailingLogObserver()
        builder_id = yield self.create_config_for_step(step)

        yield self.do_test_build(builder_id)
        yield self.assertBuildResults(1, results.EXCEPTION)
        yield self.assertStepStateString(2, "finished (exception)")
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    @defer.inlineCallbacks
    def test_Latin1ProducingCustomBuildStep(self):
        step = Latin1ProducingCustomBuildStep(logEncoding='latin-1')
        builder_id = yield self.create_config_for_step(step)

        yield self.do_test_build(builder_id)
        yield self.assertLogs(1, {
            'xx': 'o\N{CENT SIGN}\n',
        })

    @defer.inlineCallbacks
    def test_OldBuildEPYDoc(self):
        # test old-style calls to log.getText, figuring readlines will be ok
        with assertProducesWarnings(DeprecatedApiWarning, num_warnings=2,
                                    message_pattern='Subclassing old-style step'):
            step = OldBuildEPYDoc()
            builder_id = yield self.create_config_for_step(step)

            yield self.do_test_build(builder_id)
            yield self.assertBuildResults(1, results.FAILURE)

    @defer.inlineCallbacks
    def test_OldPerlModuleTest(self):
        # test old-style calls to self.getLog
        with assertProducesWarnings(DeprecatedApiWarning, num_warnings=2,
                                    message_pattern='Subclassing old-style step'):
            step = OldPerlModuleTest()
            builder_id = yield self.create_config_for_step(step)

            yield self.do_test_build(builder_id)
            yield self.assertBuildResults(1, results.SUCCESS)
