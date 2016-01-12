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

import buildbot
import mock

from buildbot import config
from buildbot import pbmanager
from buildbot import worker
from buildbot.process import botmaster
from buildbot.process import builder
from buildbot.process import factory
from buildbot.status import master
from buildbot.test.fake import fakemaster
from buildbot.test.util.decorators import flaky
from buildbot.util.eventual import eventually
from buildbot.worker import manager as workermanager
from twisted.cred import credentials
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb
from twisted.trial import unittest


class FakeSlaveBuilder(pb.Referenceable):

    """
    Fake worker-side SlaveBuilder object
    """


class FakeSlaveBuildSlave(pb.Referenceable):

    """
    Fake worker-side Worker object

    @ivar master_persp: remote perspective on the master
    """

    def __init__(self, callWhenBuilderListSet):
        self.callWhenBuilderListSet = callWhenBuilderListSet
        self.master_persp = None
        self._detach_deferreds = []
        self._detached = False

    def waitForDetach(self):
        if self._detached:
            return defer.succeed(None)
        else:
            d = defer.Deferred()
            self._detach_deferreds.append(d)
            return d

    def setMasterPerspective(self, persp):
        self.master_persp = persp
        # clear out master_persp on disconnect

        def clear_persp():
            self.master_persp = None
        persp.broker.notifyOnDisconnect(clear_persp)

        def fire_deferreds():
            self._detached = True
            self._detach_deferreds, deferreds = None, self._detach_deferreds
            for d in deferreds:
                d.callback(None)
        persp.broker.notifyOnDisconnect(fire_deferreds)

    def remote_print(self, message):
        log.msg("SLAVE-SIDE: remote_print(%r)" % (message,))

    def remote_getSlaveInfo(self):
        return {'info': 'here'}

    def remote_getVersion(self):
        return buildbot.version

    def remote_getCommands(self):
        return {'x': 1}

    def remote_setBuilderList(self, builder_info):
        builder_names = [n for n, dir in builder_info]
        slbuilders = [FakeSlaveBuilder() for n in builder_names]
        eventually(self.callWhenBuilderListSet)
        return dict(zip(builder_names, slbuilders))


class FakeBuilder(builder.Builder):

    def __init__(self, name):
        builder.Builder.__init__(self, name)
        self.builder_status = mock.Mock()

    def attached(self, slave, commands):
        assert commands == {'x': 1}
        return defer.succeed(None)

    def detached(self, slave):
        pass

    def getOldestRequestTime(self):
        return 0

    def maybeStartBuild(self):
        return defer.succeed(None)


class MyBuildSlave(worker.Worker):

    def attached(self, conn):
        self.detach_d = defer.Deferred()
        return worker.Worker.attached(self, conn)

    def detached(self):
        worker.Worker.detached(self)
        self.detach_d, d = None, self.detach_d
        d.callback(None)


class TestSlaveComm(unittest.TestCase):

    """
    Test handling of connections from workers as integrated with
     - Twisted Spread
     - real TCP connections.
     - PBManager

    @ivar master: fake build master
    @ivar pbamanger: L{PBManager} instance
    @ivar botmaster: L{BotMaster} instance
    @ivar worker: master-side L{Worker} instance
    @ivar slavebuildslave: worker-side L{FakeSlaveBuildSlave} instance
    @ivar port: TCP port to connect to
    @ivar connector: outbound TCP connection from worker to master
    """

    @defer.inlineCallbacks
    def setUp(self):
        self.master = fakemaster.make_master(testcase=self, wantMq=True,
                                             wantData=True, wantDb=True)

        # set the worker port to a loopback address with unspecified
        # port
        self.pbmanager = self.master.pbmanager = pbmanager.PBManager()
        self.pbmanager.setServiceParent(self.master)

        # remove the fakeServiceParent from fake service hierarchy, and replace by a real one
        yield self.master.workers.disownServiceParent()
        self.buildslaves = self.master.workers = workermanager.WorkerManager(self.master)
        self.buildslaves.setServiceParent(self.master)

        self.botmaster = botmaster.BotMaster()
        self.botmaster.setServiceParent(self.master)

        self.master.status = master.Status()
        self.master.status.setServiceParent(self.master)
        self.master.botmaster = self.botmaster
        self.master.data.updates.buildslaveConfigured = lambda *a, **k: None
        yield self.master.startService()

        self.buildslave = None
        self.port = None
        self.slavebuildslave = None
        self.connector = None
        self._detach_deferreds = []

        # patch in our FakeBuilder for the regular Builder class
        self.patch(botmaster, 'Builder', FakeBuilder)

    def tearDown(self):
        if self.connector:
            self.connector.disconnect()
        deferreds = self._detach_deferreds + [
            self.pbmanager.stopService(),
            self.botmaster.stopService(),
            self.buildslaves.stopService(),
        ]

        # if the worker is still attached, wait for it to detach, too
        if self.buildslave and self.buildslave.detach_d:
            deferreds.append(self.buildslave.detach_d)

        return defer.gatherResults(deferreds)

    @defer.inlineCallbacks
    def addSlave(self, **kwargs):
        """
        Create a master-side worker instance and add it to the BotMaster

        @param **kwargs: arguments to pass to the L{Worker} constructor.
        """
        self.buildslave = MyBuildSlave("testslave", "pw", **kwargs)

        # reconfig the master to get it set up
        new_config = self.master.config
        new_config.protocols = {"pb": {"port": "tcp:0:interface=127.0.0.1"}}
        new_config.workers = [self.buildslave]
        new_config.builders = [config.BuilderConfig(name='bldr',
                                                    slavename='testslave', factory=factory.BuildFactory())]

        yield self.botmaster.reconfigServiceWithBuildbotConfig(new_config)
        yield self.buildslaves.reconfigServiceWithBuildbotConfig(new_config)

        # as part of the reconfig, the worker registered with the pbmanager, so
        # get the port it was assigned
        self.port = self.buildslave.registration.getPBPort()

    def connectSlave(self, waitForBuilderList=True):
        """
        Connect a worker the master via PB

        @param waitForBuilderList: don't return until the setBuilderList has
        been called
        @returns: L{FakeSlaveBuildSlave} and a Deferred that will fire when it
        is detached; via deferred
        """
        factory = pb.PBClientFactory()
        creds = credentials.UsernamePassword("testslave", "pw")
        setBuilderList_d = defer.Deferred()
        slavebuildslave = FakeSlaveBuildSlave(
            lambda: setBuilderList_d.callback(None))

        login_d = factory.login(creds, slavebuildslave)

        @login_d.addCallback
        def logged_in(persp):
            slavebuildslave.setMasterPerspective(persp)

            # set up to hear when the worker side disconnects
            slavebuildslave.detach_d = defer.Deferred()
            persp.broker.notifyOnDisconnect(lambda:
                                            slavebuildslave.detach_d.callback(None))
            self._detach_deferreds.append(slavebuildslave.detach_d)

            return slavebuildslave

        self.connector = reactor.connectTCP("127.0.0.1", self.port, factory)

        if not waitForBuilderList:
            return login_d
        else:
            d = defer.DeferredList([login_d, setBuilderList_d],
                                   consumeErrors=True, fireOnOneErrback=True)
            d.addCallback(lambda _: slavebuildslave)
            return d

    def slaveSideDisconnect(self, slave):
        """Disconnect from the worker side"""
        slave.master_persp.broker.transport.loseConnection()

    @defer.inlineCallbacks
    def test_connect_disconnect(self):
        """Test a single worker connecting and disconnecting."""
        yield self.addSlave()

        # connect
        slave = yield self.connectSlave()

        # disconnect
        self.slaveSideDisconnect(slave)

        # wait for the resulting detach
        yield slave.waitForDetach()

    @flaky(bugNumber=2761)
    @defer.inlineCallbacks
    def test_duplicate_slave(self):
        yield self.addSlave()

        # connect first worker
        slave1 = yield self.connectSlave()

        # connect second worker; this should fail
        try:
            yield self.connectSlave(waitForBuilderList=False)
            connect_failed = False
        except Exception:
            connect_failed = True
        self.assertTrue(connect_failed)

        # disconnect both and wait for that to percolate
        self.slaveSideDisconnect(slave1)

        yield slave1.waitForDetach()

        # flush the exception logged for this on the master
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    @defer.inlineCallbacks
    def test_duplicate_slave_old_dead(self):
        yield self.addSlave()

        # connect first worker
        slave1 = yield self.connectSlave()

        # monkeypatch that worker to fail with PBConnectionLost when its
        # remote_print method is called
        def remote_print(message):
            slave1.master_persp.broker.transport.loseConnection()
            raise pb.PBConnectionLost("fake!")
        slave1.remote_print = remote_print

        # connect second worker; this should succeed, and the old worker
        # should be disconnected.
        slave2 = yield self.connectSlave()

        # disconnect both and wait for that to percolate
        self.slaveSideDisconnect(slave2)

        yield slave1.waitForDetach()

        # flush the exception logged for this on the worker
        self.assertEqual(len(self.flushLoggedErrors(pb.PBConnectionLost)), 1)
