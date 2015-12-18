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
from future.utils import iteritems

import mock

from StringIO import StringIO

from buildbot import config
from buildbot.buildslave.base import BuildSlave
from buildbot.process import builder
from buildbot.process import buildrequest
from buildbot.process import buildstep
from buildbot.process import factory
from buildbot.process import slavebuilder
from buildbot.process import results
from buildbot.steps import shell
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.fake import fakeprotocol
from twisted.internet import defer
from twisted.internet import error
from twisted.internet import reactor
from twisted.python import failure
from twisted.trial import unittest


class TestLogObserver(buildstep.LogObserver):

    def __init__(self):
        self.observed = []

    def outReceived(self, txt):
        self.observed.append(txt)


class OldStyleCustomBuildStep(buildstep.BuildStep):

    def __init__(self, arg1, arg2, doFail=False, **kwargs):
        buildstep.BuildStep.__init__(self, **kwargs)
        self.arg1 = arg1
        self.arg2 = arg2
        self.doFail = doFail

    def start(self):
        # don't complete immediately, or synchronously
        reactor.callLater(0, self.doStuff)

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

            l = self.addLog('foo')
            l.addStdout('stdout\n')
            l.addStdout(u'\N{SNOWMAN}\n'.encode('utf-8'))
            l.addStderr('stderr\n')
            l.finish()

            self.addCompleteLog('obs', 'Observer saw %r' % (lo.observed,))

            if self.doFail:
                self.failed(failure.Failure(RuntimeError('oh noes')))
            else:
                self.finished(results.SUCCESS)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.failed(failure.Failure(e))


class Latin1ProducingCustomBuildStep(buildstep.BuildStep):

    @defer.inlineCallbacks
    def run(self):
        l = yield self.addLog('xx')
        yield l.addStdout(u'\N{CENT SIGN}'.encode('latin-1'))
        yield l.finish()
        defer.returnValue(results.SUCCESS)


class FailingCustomStep(buildstep.LoggingBuildStep):

    flunkOnFailure = True

    def __init__(self, exception=buildstep.BuildStepFailed, *args, **kwargs):
        buildstep.LoggingBuildStep.__init__(self, *args, **kwargs)
        self.exception = exception

    @defer.inlineCallbacks
    def start(self):
        yield defer.succeed(None)
        raise self.exception()


class OldBuildEPYDoc(shell.ShellCommand):

    command = ['epydoc']

    def runCommand(self, cmd):
        # we don't have a real buildslave in this test harness, so fake it
        l = cmd.logs['stdio']
        l.addStdout('some\noutput\n')
        return defer.succeed(None)

    def createSummary(self, log):
        for line in StringIO(log.getText()):
            # what we do with the line isn't important to the test
            assert line in ('some\n', 'output\n')


class OldPerlModuleTest(shell.Test):

    command = ['perl']

    def runCommand(self, cmd):
        # we don't have a real buildslave in this test harness, so fake it
        l = cmd.logs['stdio']
        l.addStdout('a\nb\nc\n')
        return defer.succeed(None)

    def evaluateCommand(self, cmd):
        # Get stdio, stripping pesky newlines etc.
        lines = map(
            lambda line: line.replace('\r\n', '').replace('\r', '').replace('\n', ''),
            self.getLog('stdio').readlines()
        )
        # .. the rest of this method isn't htat interesting, as long as the
        # statement above worked
        assert lines == ['a', 'b', 'c']
        return results.SUCCESS


class RunSteps(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantMq=True, wantDb=True)
        self.master.db.insertTestData([
            fakedb.Builder(id=80, name='test'), ])

        self.builder = builder.Builder('test', _addServices=False)
        self.builder._builderid = 80
        self.builder.master = self.master
        yield self.builder.startService()

        self.factory = factory.BuildFactory()  # will have steps added later
        new_config = config.MasterConfig()
        new_config.builders.append(
            config.BuilderConfig(name='test', slavename='testsl',
                                 factory=self.factory))
        yield self.builder.reconfigServiceWithBuildbotConfig(new_config)

        self.slave = BuildSlave('bsl', 'pass')
        self.slave.sendBuilderList = lambda: defer.succeed(None)
        self.slave.parent = mock.Mock()
        self.slave.master.botmaster = mock.Mock()
        self.slave.botmaster.maybeStartBuildsForSlave = lambda sl: None
        self.slave.botmaster.getBuildersForSlave = lambda sl: []
        self.slave.parent = self.master
        self.slave.startService()
        self.conn = fakeprotocol.FakeConnection(self.master, self.slave)
        yield self.slave.attached(self.conn)

        sb = self.slavebuilder = slavebuilder.SlaveBuilder()
        sb.setBuilder(self.builder)
        yield sb.attached(self.slave, {})

        # add the buildset/request
        self.bsid, brids = yield self.master.db.buildsets.addBuildset(
            sourcestamps=[{}], reason=u'x', properties={},
            builderids=[80], waited_for=False)

        self.brdict = \
            yield self.master.db.buildrequests.getBuildRequest(brids[80])

        self.buildrequest = \
            yield buildrequest.BuildRequest.fromBrdict(self.master, self.brdict)

    def tearDown(self):
        return self.builder.stopService()

    @defer.inlineCallbacks
    def do_test_step(self):
        # patch builder.buildFinished to signal us with a deferred
        bfd = defer.Deferred()
        old_buildFinished = self.builder.buildFinished

        def buildFinished(*args):
            old_buildFinished(*args)
            bfd.callback(None)
        self.builder.buildFinished = buildFinished

        # start the builder
        self.failUnless((yield self.builder.maybeStartBuild(
            self.slavebuilder, [self.buildrequest])))

        # and wait for completion
        yield bfd

        # then get the BuildStatus and return it
        defer.returnValue(self.master.status.lastBuilderStatus.lastBuildStatus)

    def assertLogs(self, exp_logs):
        got_logs = {}
        for id, l in iteritems(self.master.data.updates.logs):
            self.failUnless(l['finished'])
            got_logs[l['name']] = ''.join(l['content'])
        self.assertEqual(got_logs, exp_logs)

    @defer.inlineCallbacks
    def doOldStyleCustomBuildStep(self, slowDB=False):
        # patch out addLog to delay until we're ready
        newLogDeferreds = []
        oldNewLog = self.master.data.updates.addLog

        def finishNewLog(self):
            for d in newLogDeferreds:
                reactor.callLater(0, d.callback, None)

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

        self.factory.addStep(OldStyleCustomBuildStep(arg1=1, arg2=2))
        yield self.do_test_step()

        self.assertLogs({
            u'compl.html': u'<blink>A very short logfile</blink>\n',
            # this is one of the things that differs independently of
            # new/old style: encoding of logs and newlines
            u'foo':
            # 'stdout\n\xe2\x98\x83\nstderr\n',
            u'ostdout\no\N{SNOWMAN}\nestderr\n',
            u'obs':
            # if slowDB, the observer wont see anything before the end of this instant step
            u'Observer saw []\n' if slowDB else
            # 'Observer saw [\'stdout\\n\', \'\\xe2\\x98\\x83\\n\']',
            u'Observer saw [u\'stdout\\n\', u\'\\u2603\\n\']\n',
        })

    def test_OldStyleCustomBuildStep(self):
        return self.doOldStyleCustomBuildStep(False)

    def test_OldStyleCustomBuildStepSlowDB(self):
        return self.doOldStyleCustomBuildStep(True)

    @defer.inlineCallbacks
    def test_OldStyleCustomBuildStep_failure(self):
        self.factory.addStep(OldStyleCustomBuildStep(arg1=1, arg2=2, doFail=1))
        bs = yield self.do_test_step()
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        self.assertEqual(bs.getResults(), results.EXCEPTION)

    @defer.inlineCallbacks
    def test_step_raising_buildstepfailed_in_start(self):
        self.factory.addStep(FailingCustomStep())
        bs = yield self.do_test_step()
        self.assertEqual(bs.getResults(), results.FAILURE)

    @defer.inlineCallbacks
    def test_step_raising_exception_in_start(self):
        self.factory.addStep(FailingCustomStep(exception=ValueError))
        bs = yield self.do_test_step()
        self.assertEqual(bs.getResults(), results.EXCEPTION)
        self.assertEqual(len(self.flushLoggedErrors(ValueError)), 1)

    @defer.inlineCallbacks
    def test_step_raising_connectionlost_in_start(self):
        self.factory.addStep(FailingCustomStep(exception=error.ConnectionLost))
        bs = yield self.do_test_step()
        self.assertEqual(bs.getResults(), results.RETRY)

    @defer.inlineCallbacks
    def test_Latin1ProducingCustomBuildStep(self):
        self.factory.addStep(Latin1ProducingCustomBuildStep(logEncoding='latin-1'))
        yield self.do_test_step()
        self.assertLogs({
            u'xx': u'o\N{CENT SIGN}\n',
        })

    @defer.inlineCallbacks
    def test_OldBuildEPYDoc(self):
        # test old-style calls to log.getText, figuring readlines will be ok
        self.factory.addStep(OldBuildEPYDoc())
        bs = yield self.do_test_step()
        self.assertEqual(bs.getResults(), results.FAILURE)

    @defer.inlineCallbacks
    def test_OldPerlModuleTest(self):
        # test old-style calls to self.getLog
        self.factory.addStep(OldPerlModuleTest())
        bs = yield self.do_test_step()
        self.assertEqual(bs.getResults(), results.SUCCESS)
