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
import os

from buildbot import config
from buildbot import master
from buildbot import util
from buildbot.clients import tryclient
from buildbot.schedulers import trysched
from buildbot.status import client
from buildbot.test.util import dirs
from buildbot.test.util.flaky import flaky
from twisted.cred import credentials
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb
from twisted.trial import unittest


# wait for some asynchronous result
@defer.inlineCallbacks
def waitFor(fn):
    while True:
        res = yield fn()
        if res:
            defer.returnValue(res)
        yield util.asyncSleep(.01)


class FakeRemoteSlave(pb.Referenceable):
    # the bare minimum to connect to a master and convince it that the slave is
    # ready

    def __init__(self, port):
        self.port = port

    @defer.inlineCallbacks
    def start(self):
        f = pb.PBClientFactory()
        d = f.login(credentials.UsernamePassword('local1', 'localpw'), self)
        reactor.connectTCP('127.0.0.1', self.port, f)
        # we need to hold a reference to this, otherwise the broker will sever
        # the connection
        self.mind = yield d

    def stop(self):
        self.mind.broker.transport.loseConnection()
        self.mind = None

    # BuildSlave methods

    def remote_print(self, message):
        log.msg("from master: %s" % (message,))

    def remote_getSlaveInfo(self):
        return {}

    def remote_getCommands(self):
        return {}

    def remote_getVersion(self):
        return '0.0'

    def remote_setMaster(self, master):
        pass

    def remote_setBuilderList(self, wanted):
        return {'a': self}

    def remote_startBuild(self):
        return


class Schedulers(dirs.DirsMixin, unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.abspath('basedir')
        self.setUpDirs(self.basedir)

        self.configfile = os.path.join(self.basedir, 'master.cfg')
        open(self.configfile, "w").write(
            'from buildbot.test.integration.test_try_client \\\n'
            'import BuildmasterConfig\n')

        self.master = None
        self.sch = None
        self.slave = None

        def spawnProcess(pp, executable, args, environ):
            assert executable == 'ssh'
            tmpfile = os.path.join(self.jobdir, 'tmp', 'testy')
            newfile = os.path.join(self.jobdir, 'new', 'testy')
            open(tmpfile, "w").write(pp.job)
            os.rename(tmpfile, newfile)
            log.msg("wrote jobfile %s" % newfile)
            # get the scheduler to poll this directory now
            d = self.sch.watcher.poll()
            d.addErrback(log.err, 'while polling')

            def finished(_):
                st = mock.Mock()
                st.value.signal = None
                st.value.exitCode = 0
                pp.processEnded(st)
            d.addCallback(finished)

        self.patch(reactor, 'spawnProcess', spawnProcess)

        def getSourceStamp(vctype, treetop, branch=None, repository=None):
            return defer.succeed(
                tryclient.SourceStamp(branch='br', revision='rr',
                                      patch=(0, '++--')))
        self.patch(tryclient, 'getSourceStamp', getSourceStamp)

        self.output = []

        # stub out printStatus, as it's timing-based and thus causes
        # occasional test failures.
        self.patch(tryclient.Try, 'printStatus', lambda: None)

        def output(*msg):
            msg = ' '.join(map(str, msg))
            log.msg("output: %s" % msg)
            self.output.append(msg)
        self.patch(tryclient, 'output', output)

    @defer.inlineCallbacks
    def tearDown(self):
        if self.slave:
            log.msg("stopping slave")
            yield self.slave.stop()
        if self.master:
            log.msg("stopping master")
            yield self.master.stopService()
            if self.master.db.pool:
                log.msg("stopping master db pool")
                yield self.master.db.pool.shutdown()
        log.msg("tearDown complete")
        yield self.tearDownDirs()

    def setupJobdir(self):
        self.jobdir = os.path.join(self.basedir, 'jobs')
        for sub in 'new', 'tmp', 'cur':
            p = os.path.join(self.jobdir, sub)
            os.makedirs(p)
        return self.jobdir

    @defer.inlineCallbacks
    def startMaster(self, sch, startSlave=False, wantPBListener=False):
        BuildmasterConfig['schedulers'] = [sch]
        self.sch = sch

        if wantPBListener:
            self.pblistener = client.PBListener(0)
            BuildmasterConfig['status'] = [self.pblistener]
        else:
            BuildmasterConfig['status'] = []

        # create the master and set its config
        m = self.master = master.BuildMaster(self.basedir, self.configfile)
        m.config = config.MasterConfig.loadConfig(
            self.basedir, self.configfile)

        # set up the db
        yield m.db.setup(check_version=False)
        yield m.db.model.create()

        # stub out m.db.setup since it was already called above
        m.db.setup = lambda: None

        # mock reactor.stop (which trial *really* doesn't
        # like test code to call!)
        mock_reactor = mock.Mock(spec=reactor)
        mock_reactor.callWhenRunning = reactor.callWhenRunning

        # start the service
        yield m.startService(_reactor=mock_reactor)
        self.failIf(mock_reactor.stop.called,
                    "startService tried to stop the reactor; check logs")

        # hang out until the scheduler has registered its PB port
        if isinstance(self.sch, trysched.Try_Userpass):
            def getSchedulerPort():
                if not self.sch.registrations:
                    return
                self.serverPort = self.sch.registrations[0].getPort()
                log.msg("Scheduler registered at port %d" % self.serverPort)
                return True
            yield waitFor(getSchedulerPort)

        # now start the fake slave
        if startSlave:
            self.slave = FakeRemoteSlave(self.serverPort)
            yield self.slave.start()

    def runClient(self, config):
        self.clt = tryclient.Try(config)
        return self.clt.run(_inTests=True)

    @defer.inlineCallbacks
    def test_userpass_no_wait(self):
        yield self.startMaster(
            trysched.Try_Userpass('try', ['a'], 0, [('u', 'p')]),
            startSlave=False)
        yield self.runClient({
            'connect': 'pb',
            'master': '127.0.0.1:%s' % self.serverPort,
            'username': 'u',
            'passwd': 'p',
        })
        self.assertEqual(self.output, [
            "using 'pb' connect method",
            'job created',
            'Delivering job; comment= None',
            'job has been delivered',
            'not waiting for builds to finish'
        ])
        buildsets = yield self.master.db.buildsets.getBuildsets()
        self.assertEqual(len(buildsets), 1)

    @flaky(bugNumber=2762)
    @defer.inlineCallbacks
    def test_userpass_wait(self):
        yield self.startMaster(
            trysched.Try_Userpass('try', ['a'], 0, [('u', 'p')]),
            startSlave=True)
        yield self.runClient({
            'connect': 'pb',
            'master': '127.0.0.1:%s' % self.serverPort,
            'username': 'u',
            'passwd': 'p',
            'wait': True,
        })
        self.assertEqual(self.output, [
            "using 'pb' connect method",
            'job created',
            'Delivering job; comment= None',
            'job has been delivered',
            'All Builds Complete',
            'a: success (build successful)',
        ])
        buildsets = yield self.master.db.buildsets.getBuildsets()
        self.assertEqual(len(buildsets), 1)

    @defer.inlineCallbacks
    def test_userpass_list_builders(self):
        yield self.startMaster(
            trysched.Try_Userpass('try', ['a'], 0, [('u', 'p')]),
            startSlave=False)
        yield self.runClient({
            'connect': 'pb',
            'get-builder-names': True,
            'master': '127.0.0.1:%s' % self.serverPort,
            'username': 'u',
            'passwd': 'p',
        })
        self.assertEqual(self.output, [
            "using 'pb' connect method",
            'The following builders are available for the try scheduler: ',
            'a'
        ])
        buildsets = yield self.master.db.buildsets.getBuildsets()
        self.assertEqual(len(buildsets), 0)

    @defer.inlineCallbacks
    def test_jobdir_no_wait(self):
        jobdir = self.setupJobdir()
        yield self.startMaster(
            trysched.Try_Jobdir('try', ['a'], jobdir),
            startSlave=False,
            wantPBListener=True)
        yield self.runClient({
            'connect': 'ssh',
            'master': '127.0.0.1',
            'username': 'u',
            'passwd': 'p',
            'builders': 'a',  # appears to be required for ssh
        })
        self.assertEqual(self.output, [
            "using 'ssh' connect method",
            'job created',
            'job has been delivered',
            'not waiting for builds to finish'
        ])
        buildsets = yield self.master.db.buildsets.getBuildsets()
        self.assertEqual(len(buildsets), 1)

    @defer.inlineCallbacks
    def test_jobdir_wait(self):
        jobdir = self.setupJobdir()
        yield self.startMaster(
            trysched.Try_Jobdir('try', ['a'], jobdir),
            startSlave=False)
        yield self.runClient({
            'connect': 'ssh',
            'wait': True,
            'host': '127.0.0.1',
            'username': 'u',
            'passwd': 'p',
            'builders': 'a',  # appears to be required for ssh
        })
        self.assertEqual(self.output, [
            "using 'ssh' connect method",
            'job created',
            'job has been delivered',
            'waiting for builds with ssh is not supported'
        ])
        buildsets = yield self.master.db.buildsets.getBuildsets()
        self.assertEqual(len(buildsets), 1)


c = BuildmasterConfig = {}
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig
from buildbot.process.buildstep import BuildStep
from buildbot.process.factory import BuildFactory
from buildbot.status import results


class MyBuildStep(BuildStep):

    def start(self):
        self.finished(results.SUCCESS)


c['slaves'] = [BuildSlave("local1", "localpw")]
c['slavePortnum'] = 0
c['change_source'] = []
c['schedulers'] = []  # filled in above
f1 = BuildFactory()
f1.addStep(MyBuildStep(name='one'))
f1.addStep(MyBuildStep(name='two'))
c['builders'] = [
    BuilderConfig(name="a", slavenames=["local1"], factory=f1),
]
c['status'] = []
c['title'] = "test"
c['titleURL'] = "test"
c['buildbotURL'] = "http://localhost:8010/"
c['db'] = {'db_url': "sqlite:///state.sqlite"}
