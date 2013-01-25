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
from twisted.spread import pb
from twisted.internet import defer, reactor
from twisted.cred import credentials
from twisted.trial import unittest
from twisted.python import log
import buildbot
from buildbot.test.util import compat
from buildbot.process import botmaster, builder, factory
from buildbot import pbmanager, buildslave, config
from buildbot.status import master
from buildbot.util.eventual import eventually
from buildbot.test.fake import fakemaster

class FakeSlaveBuilder(pb.Referenceable):
    """
    Fake slave-side SlaveBuilder object
    """

class FakeSlaveBuildSlave(pb.Referenceable):
    """
    Fake slave-side BuildSlave object

    @ivar master_persp: remote perspective on the master
    """

    def __init__(self, callWhenBuilderListSet):
        self.callWhenBuilderListSet = callWhenBuilderListSet
        self.master_persp = None

    def setMasterPerspective(self, persp):
        self.master_persp = persp
        # clear out master_persp on disconnect
        def clear_persp():
            self.master_persp = None
        persp.broker.notifyOnDisconnect(clear_persp)

    def remote_print(self, what):
        log.msg("SLAVE-SIDE: remote_print(%r)" % (what,))

    def remote_getSlaveInfo(self):
        return { 'info' : 'here' }

    def remote_getVersion(self):
        return buildbot.version

    def remote_getCommands(self):
        return { 'x' : 1 }

    def remote_setBuilderList(self, builder_info):
        builder_names = [ n for n, dir in builder_info ]
        slbuilders = [ FakeSlaveBuilder() for n in builder_names ]
        eventually(self.callWhenBuilderListSet)
        return dict(zip(builder_names, slbuilders))


class FakeBuilder(builder.Builder):

    def __init__(self, name):
        builder.Builder.__init__(self, name)
        self.builder_status = mock.Mock()

    def attached(self, slave, remote, commands):
        assert commands == { 'x' : 1 }
        return defer.succeed(None)

    def detached(self, slave):
        pass

    def getOldestRequestTime(self):
        return 0

    def maybeStartBuild(self):
        return defer.succeed(None)


class TestSlaveComm(unittest.TestCase):
    """
    Test handling of connections from slaves as integrated with
     - Twisted Spread
     - real TCP connections.
     - PBManager

    @ivar master: fake build master
    @ivar pbamanger: L{PBManager} instance
    @ivar botmaster: L{BotMaster} instance
    @ivar buildslave: master-side L{BuildSlave} instance
    @ivar slavebuildslave: slave-side L{FakeSlaveBuildSlave} instance
    @ivar port: TCP port to connect to
    @ivar connector: outbound TCP connection from slave to master
    @ivar detach_d: Defererd that will fire when C{buildslave.detached} is
    called
    """

    def setUp(self):
        self.master = fakemaster.make_master()
        # set the slave port to a loopback address with unspecified
        # port
        self.pbmanager = self.master.pbmanager = pbmanager.PBManager()
        self.pbmanager.startService()

        self.botmaster = botmaster.BotMaster(self.master)
        self.botmaster.startService()

        self.master.status = master.Status(self.master)

        self.buildslave = None
        self.port = None
        self.slavebuildslave = None
        self.connector = None
        self.detach_d = None

    def tearDown(self):
        if self.connector:
            self.connector.disconnect()
        return defer.gatherResults([
            self.pbmanager.stopService(),
            self.botmaster.stopService(),
        ])

    @defer.inlineCallbacks
    def addSlave(self, **kwargs):
        """
        Create a master-side slave instance and add it to the BotMaster

        @param **kwargs: arguments to pass to the L{BuildSlave} constructor.
        """
        self.buildslave = buildslave.BuildSlave("testslave", "pw", **kwargs)

        # patch in our FakeBuilder for the regular Builder class
        self.patch(botmaster, 'Builder', FakeBuilder)

        # reconfig the master to get it set up
        new_config = self.master.config
        new_config.slavePortnum = "tcp:0:interface=127.0.0.1"
        new_config.slaves = [ self.buildslave ]
        new_config.builders = [ config.BuilderConfig(name='bldr',
                slavename='testslave', factory=factory.BuildFactory()) ]

        yield self.botmaster.reconfigService(new_config)

        # as part of the reconfig, the slave registered with the pbmanager, so
        # get the port it was assigned
        self.port = self.buildslave.registration.getPort()

    def connectSlave(self, waitForBuilderList=True):
        """
        Connect a slave the master via PB

        @param waitForBuilderList: don't return until the setBuilderList has
        been called
        @returns: L{FakeSlaveBuildSlave} and a Deferred that will fire when it
        is detached; via deferred
        """
        factory = pb.PBClientFactory()
        creds = credentials.UsernamePassword("testslave", "pw")
        setBuilderList_d = defer.Deferred()
        slavebuildslave = FakeSlaveBuildSlave(
                lambda : setBuilderList_d.callback(None))

        login_d = factory.login(creds, slavebuildslave)
        def logged_in(persp):
            slavebuildslave.setMasterPerspective(persp)

            self.detach_d = defer.Deferred()
            self.buildslave.subscribeToDetach(lambda :
                        self.detach_d.callback(None))

            return slavebuildslave
        login_d.addCallback(logged_in)

        self.connector = reactor.connectTCP("127.0.0.1", self.port, factory)

        if not waitForBuilderList:
            return login_d
        else:
            d = defer.DeferredList([login_d, setBuilderList_d],
                                   consumeErrors=True, fireOnOneErrback=True)
            d.addCallback(lambda _ : slavebuildslave)
            return d

    def slaveSideDisconnect(self, slave):
        """Disconnect from the slave side"""
        slave.master_persp.broker.transport.loseConnection()

    @defer.inlineCallbacks
    def test_connect_disconnect(self):
        """Test a single slave connecting and disconnecting."""
        yield self.addSlave()

        # connect
        slave = yield self.connectSlave()

        # disconnect
        self.slaveSideDisconnect(slave)

        # wait for the resulting detach
        yield self.detach_d

    @defer.inlineCallbacks
    @compat.usesFlushLoggedErrors
    def test_duplicate_slave(self):
        yield self.addSlave()

        # connect first slave
        slave1 = yield self.connectSlave()

        # connect second slave; this should fail
        try:
            yield self.connectSlave(waitForBuilderList=False)
            connect_failed = False
        except:
            connect_failed = True
        self.assertTrue(connect_failed)

        # disconnect both and wait for that to percolate
        self.slaveSideDisconnect(slave1)

        yield self.detach_d

        # flush the exception logged for this on the master
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    @defer.inlineCallbacks
    @compat.usesFlushLoggedErrors
    def test_duplicate_slave_old_dead(self):
        yield self.addSlave()

        # connect first slave
        slave1 = yield self.connectSlave()

        # monkeypatch that slave to fail with PBConnectionLost when its
        # remote_print method is called
        def remote_print(what):
            raise pb.PBConnectionLost("fake!")
        slave1.remote_print = remote_print

        # connect second slave; this should succeed, and the old slave
        # should be disconnected.
        slave2 = yield self.connectSlave()

        # disconnect both and wait for that to percolate
        self.slaveSideDisconnect(slave2)

        yield self.detach_d

        # flush the exception logged for this on the slave
        self.assertEqual(len(self.flushLoggedErrors(pb.PBConnectionLost)), 1)
