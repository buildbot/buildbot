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

from StringIO import StringIO

from buildbot import config
from buildbot import util
from buildbot.buildslave.base import BuildSlave
from buildbot.process import builder
from buildbot.process import buildrequest
from buildbot.process import buildstep
from buildbot.process import factory
from buildbot.process import slavebuilder
from buildbot.process import remotecommand
from buildbot.status import results
from buildbot.steps import shell
from buildbot.test.fake import fakemaster
from twisted.internet import defer
from twisted.internet import error
from twisted.internet import reactor
from twisted.python import failure
from twisted.trial import unittest
from twisted.spread import pb


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
        except Exception, e:
            import traceback
            traceback.print_exc()
            self.failed(failure.Failure(e))


class NewStyleCustomBuildStep(buildstep.BuildStep):

    @defer.inlineCallbacks
    def run(self):
        def dCheck(d):
            if not isinstance(d, defer.Deferred):
                raise AssertionError("expected Deferred")
            return d

        # don't complete immediately, or synchronously
        yield util.asyncSleep(0)

        lo = TestLogObserver()
        self.addLogObserver('testlog', lo)

        log = yield dCheck(self.addLog('testlog'))
        yield dCheck(log.addStdout(u'stdout\n'))

        yield dCheck(self.addCompleteLog('obs',
                'Observer saw %r' % (map(unicode, lo.observed),)))
        yield dCheck(self.addHTMLLog('foo.html', '<head>\n'))
        yield dCheck(self.addURL('linkie', 'http://foo'))

        cmd = remotecommand.RemoteCommand('fake', {})
        cmd.useLog(log)
        stdio = yield dCheck(self.addLog('stdio'))
        cmd.useLog(stdio)
        yield dCheck(cmd.addStdout(u'stdio\n'))
        yield dCheck(cmd.addStderr(u'stderr\n'))
        yield dCheck(cmd.addHeader(u'hdr\n'))
        yield dCheck(cmd.addToLog('testlog', 'fromcmd\n'))

        yield dCheck(log.finish())

        defer.returnValue(results.SUCCESS)


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


class FakeBot():

    def __init__(self):
        self.commands = []
        info = {'basedir': '/sl'}
        doNothing = lambda *args: defer.succeed(None)
        self.response = {
            'getSlaveInfo': lambda: defer.succeed(info),
            'setMaster': doNothing,
            'print': doNothing,
            'startBuild': doNothing,
        }

    def notifyOnDisconnect(self, cb):
        pass

    def dontNotifyOnDisconnect(self, cb):
        pass

    def callRemote(self, command, *args):
        self.commands.append((command,) + args)
        response = self.response.get(command)
        if response:
            return response(*args)
        else:
            return defer.fail(pb.NoSuchMethod(command))


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
        self.master = fakemaster.make_master(testcase=self, wantDb=True)
        self.builder = builder.Builder('test', _addServices=False)
        self.builder.master = self.master
        yield self.builder.startService()

        self.factory = factory.BuildFactory()  # will have steps added later
        new_config = config.MasterConfig()
        new_config.builders.append(
            config.BuilderConfig(name='test', slavename='testsl',
                                 factory=self.factory))
        yield self.builder.reconfigService(new_config)

        self.slave = BuildSlave('bsl', 'pass')
        self.slave.sendBuilderList = lambda: defer.succeed(None)
        self.slave.botmaster = mock.Mock()
        self.slave.botmaster.maybeStartBuildsForSlave = lambda sl: None
        self.slave.master = self.master
        self.slave.startService()
        self.remote = FakeBot()
        yield self.slave.attached(self.remote)

        sb = self.slavebuilder = slavebuilder.SlaveBuilder()
        sb.setBuilder(self.builder)
        yield sb.attached(self.slave, self.remote, {})

        # add the buildset/request
        sssid = yield self.master.db.sourcestampsets.addSourceStampSet()
        yield self.master.db.sourcestamps.addSourceStamp(branch='br',
                revision='1', repository='r://', project='',
                sourcestampsetid=sssid)
        self.bsid, brids = yield self.master.db.buildsets.addBuildset(
            sourcestampsetid=sssid, reason=u'x', properties={},
            builderNames=['test'])

        self.brdict = \
            yield self.master.db.buildrequests.getBuildRequest(brids['test'])

        self.buildrequest = \
            yield buildrequest.BuildRequest.fromBrdict(self.master, self.brdict)

    def tearDown(self):
        self.slave.stopKeepaliveTimer()
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
        bs = self.master.status.lastBuilderStatus.lastBuildStatus
        # tell the steps they're not new-style anymore, so they don't assert
        for l in bs.getLogs():
            l._isNewStyle = False
        got_logs = dict((l.name, l.getText()) for l in bs.getLogs())
        self.assertEqual(got_logs, exp_logs)

    @defer.inlineCallbacks
    def test_OldStyleCustomBuildStep(self):
        self.factory.addStep(OldStyleCustomBuildStep(arg1=1, arg2=2))
        yield self.do_test_step()

        self.assertLogs({
            u'compl.html': u'<blink>A very short logfile</blink>\n',
            # this is one of the things that differs independently of
            # new/old style: encoding of logs and newlines
            u'foo':
                'stdout\n\xe2\x98\x83\nstderr\n',
                #u'ostdout\no\N{SNOWMAN}\nestderr\n',
            u'obs':
                'Observer saw [\'stdout\\n\', \'\\xe2\\x98\\x83\\n\']',
                #u'Observer saw [u\'stdout\\n\', u\'\\u2603\\n\']\n',
        })

    @defer.inlineCallbacks
    def test_OldStyleCustomBuildStep_failure(self):
        self.factory.addStep(OldStyleCustomBuildStep(arg1=1, arg2=2, doFail=1))
        bs = yield self.do_test_step()
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        self.assertEqual(bs.getResults(), results.EXCEPTION)

    @defer.inlineCallbacks
    def test_NewStyleCustomBuildStep(self):
        self.factory.addStep(NewStyleCustomBuildStep())
        yield self.do_test_step()
        self.assertLogs({
            'foo.html': '<head>\n',
            'testlog': 'stdout\nfromcmd\n',
            'obs': "Observer saw [u'stdout\\n']",
            'stdio': "stdio\nstderr\n",
        })

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
        #self.expectOutcome(result=EXCEPTION, status_text=["generic", "exception"])
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
    test_Latin1ProducingCustomBuildStep.skip = "logEncoding not supported in 0.8.x"

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
