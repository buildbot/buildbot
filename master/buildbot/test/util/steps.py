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
from twisted.spread import pb

from buildbot import config
from buildbot import interfaces
from buildbot.buildslave.base import BuildSlave
from buildbot.process import builder
from buildbot.process import buildrequest
from buildbot.process import buildstep
from buildbot.process import factory
from buildbot.process import remotecommand as real_remotecommand
from buildbot.process import slavebuilder
from buildbot.test.fake import fakebuild
from buildbot.test.fake import fakemaster
from buildbot.test.fake import remotecommand
from buildbot.test.fake import slave


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
    @ivar step_status: mock StepStatus object
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

    def setupStep(self, step, slave_version={'*': "99.99"}, slave_env={}):
        """
        Set up C{step} for testing.  This begins by using C{step} as a factory
        to create a I{new} step instance, thereby testing that the the factory
        arguments are handled correctly.  It then creates a comfortable
        environment for the slave to run in, repleate with a fake build and a
        fake slave.

        As a convenience, it calls the step's setDefaultWorkdir method with
        C{'wkdir'}.

        @param slave_version: slave version to present, as a dictionary mapping
            command name to version.  A command name of '*' will apply for all
            commands.

        @param slave_env: environment from the slave at slave startup
        """
        fctry = interfaces.IBuildStepFactory(step)
        step = self.step = fctry.buildStep()
        self.master = fakemaster.make_master(testcase=self)

        # step.build

        b = self.build = fakebuild.FakeBuild(master=self.master)
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

        self.master = fakemaster.make_master(testcase=self)
        self.buildslave = step.buildslave = slave.FakeSlave(self.master)

        # step.step_status

        ss = self.step_status = mock.Mock(name="step_status")

        ss.status_text = None
        ss.logs = {}

        def ss_setText(strings):
            ss.status_text = strings
        ss.setText = ss_setText

        ss.getLogs = lambda: ss.logs.values()

        self.step_statistics = {}
        ss.setStatistic = self.step_statistics.__setitem__
        ss.getStatistic = self.step_statistics.get
        ss.hasStatistic = self.step_statistics.__contains__

        self.step.setStepStatus(ss)

        # step overrides

        def addLog(name):
            l = remotecommand.FakeLogFile(name, step)
            ss.logs[name] = l
            return l
        step.addLog = addLog

        def addHTMLLog(name, html):
            l = remotecommand.FakeLogFile(name, step)
            l.addStdout(html)
            ss.logs[name] = l
            return l
        step.addHTMLLog = addHTMLLog

        def addCompleteLog(name, text):
            l = remotecommand.FakeLogFile(name, step)
            l.addStdout(text)
            ss.logs[name] = l
            return l
        step.addCompleteLog = addCompleteLog

        step.logobservers = self.logobservers = {}

        def addLogObserver(logname, observer):
            self.logobservers.setdefault(logname, []).append(observer)
            observer.step = step
        step.addLogObserver = addLogObserver

        # add any observers defined in the constructor, before this monkey-patch
        for n, o in step._pendingLogObservers:
            addLogObserver(n, o)

        # set defaults

        step.setDefaultWorkdir('wkdir')

        # expectations

        self.exp_outcome = None
        self.exp_properties = {}
        self.exp_missing_properties = []
        self.exp_logfiles = {}
        self.exp_hidden = False

        # check that the step's name is not None
        self.assertNotEqual(step.name, None)

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
        self.remote = mock.Mock(name="SlaveBuilder(remote)")
        # TODO: self.step.setupProgress()
        d = self.step.startStep(self.remote)

        def check(result):
            self.assertEqual(self.expected_remote_commands, [],
                             "assert all expected commands were run")
            got_outcome = dict(result=result,
                               status_text=self.step_status.status_text)
            self.assertEqual(got_outcome, self.exp_outcome,
                             "expected step outcome")
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
                    self.step_status.logs[l].stdout, contents, "log '%s' contents" % l)
            self.step_status.setHidden.assert_called_once_with(self.exp_hidden)
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


class BuildStepIntegrationMixin(object):

    """Support for *integration* testing of buildsteps.  This class runs as
    much "real" code as possible, unlike BuildStepMixin which focuses on the
    step itself."""

    @defer.inlineCallbacks
    def setUpBuildStepIntegration(self):
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

    def tearDownBuildStepIntegration(self):
        self.slave.stopKeepaliveTimer()
        return self.builder.stopService()

    def setupStep(self, step):
        self.factory.addStep(step)

    @defer.inlineCallbacks
    def runStep(self):
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
