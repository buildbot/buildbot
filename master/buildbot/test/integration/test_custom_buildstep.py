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

from buildbot import config
from buildbot.buildslave.base import BuildSlave
from buildbot.process import builder
from buildbot.process import buildrequest
from buildbot.process import buildstep
from buildbot.process import factory
from buildbot.process import slavebuilder
from buildbot.status import results
from buildbot.test.fake import fakemaster
from buildbot.test.fake import fakeprotocol
from twisted.internet import defer
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


class FailingCustomStep(buildstep.LoggingBuildStep):

    flunkOnFailure = True

    def __init__(self, exception=buildstep.BuildStepFailed, *args, **kwargs):
        buildstep.LoggingBuildStep.__init__(self, *args, **kwargs)
        self.exception = exception

    @defer.inlineCallbacks
    def start(self):
        yield defer.succeed(None)
        raise self.exception()


class RunSteps(unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantMq=True, wantDb=True)
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
        self.conn = fakeprotocol.FakeConnection(self.master, self.slave)
        yield self.slave.attached(self.conn)

        sb = self.slavebuilder = slavebuilder.SlaveBuilder()
        sb.setBuilder(self.builder)
        yield sb.attached(self.slave, {})

        # add the buildset/request
        self.bsid, brids = yield self.master.db.buildsets.addBuildset(
            sourcestamps=[{}], reason=u'x', properties={},
            builderNames=['test'], waited_for=False)

        self.brdict = \
            yield self.master.db.buildrequests.getBuildRequest(brids['test'])

        self.buildrequest = \
            yield buildrequest.BuildRequest.fromBrdict(self.master, self.brdict)

    def tearDown(self):
        return self.builder.stopService()

    @defer.inlineCallbacks
    def do_test_step(self):
        # patch builder.buildFinished to signal us with a deferred
        bfd = defer.Deferred()
        old_buildFinished = self.builder.buildFinished

        def buildFinished(build, sb, bids):
            old_buildFinished(build, sb, bids)
            bfd.callback(None)
        self.builder.buildFinished = buildFinished

        # start the builder
        self.failUnless((yield self.builder.maybeStartBuild(
            self.slavebuilder, [self.buildrequest])))

        # and wait for completion
        yield bfd

        # then get the BuildStatus and return it
        defer.returnValue(self.master.status.lastBuilderStatus.lastBuildStatus)

    @defer.inlineCallbacks
    def test_OldStyleCustomBuildStep(self):
        self.factory.addStep(OldStyleCustomBuildStep(arg1=1, arg2=2))
        bs = yield self.do_test_step()
        logs = dict((l.name, l.old_getText()) for l in bs.getLogs())
        self.assertEqual(logs, {
            'compl.html': '<blink>A very short logfile</blink>\n',
            'foo': 'stdout\nstderr\n',
            'obs': 'Observer saw [\'stdout\\n\']',
        })

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
        # , status_text=["generic"])
        self.assertEqual(bs.getResults(), results.FAILURE)

    @defer.inlineCallbacks
    def test_step_raising_exception_in_start(self):
        self.factory.addStep(FailingCustomStep(exception=ValueError))
        bs = yield self.do_test_step()
        self.assertEqual(bs.getResults(), results.EXCEPTION)
        #self.expectOutcome(result=EXCEPTION, status_text=["generic", "exception"])
        self.assertEqual(len(self.flushLoggedErrors(ValueError)), 1)
