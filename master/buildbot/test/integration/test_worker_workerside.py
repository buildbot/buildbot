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
import os
import shutil
import tempfile
import time

import mock

from twisted.cred.error import UnauthorizedLogin
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import util
from twisted.trial import unittest

import buildbot_worker.bot
from buildbot import config
from buildbot import pbmanager
from buildbot import worker
from buildbot.process import botmaster
from buildbot.process import builder
from buildbot.process import factory
from buildbot.status import master
from buildbot.test.fake import fakemaster
from buildbot.test.util.misc import TestReactorMixin
from buildbot.worker import manager as workermanager

PKI_DIR = util.sibpath(__file__, 'pki')

# listening on port 0 says to the kernel to choose any free port (race-free)
# the environment variable is handy for repetitive test launching with
# introspecting tools (tcpdump, wireshark...)
DEFAULT_PORT = os.environ.get("BUILDBOT_TEST_DEFAULT_PORT", "0")


class FakeBuilder(builder.Builder):

    def __init__(self, name):
        super().__init__(name)
        self.builder_status = mock.Mock()

    def attached(self, worker, commands):
        return defer.succeed(None)

    def detached(self, worker):
        pass

    def getOldestRequestTime(self):
        return 0

    def maybeStartBuild(self):
        return defer.succeed(None)


class MasterSideWorker(worker.Worker):

    detach_d = None

    def attached(self, conn):
        self.detach_d = defer.Deferred()
        return super().attached(conn)

    def detached(self):
        super().detached()
        self.detach_d, d = None, self.detach_d
        d.callback(None)


class TestingWorker(buildbot_worker.bot.Worker):
    """Add more introspection and scheduling hooks to the real Worker class.

    @ivar tests_connected: a ``Deferred`` that's called back once the PB
                           connection is operational (``gotPerspective``).
                           Callbacks receive the ``Perspective`` object.
    @ivar tests_disconnected: a ``Deferred`` that's called back upon
                              disconnections.

    yielding these in an inlineCallbacks has the effect to wait on the
    corresponding conditions, actually allowing the services to fulfill them.
    """

    def __init__(self, *args, **kwargs):
        super(TestingWorker, self).__init__(*args, **kwargs)

        self.tests_disconnected = defer.Deferred()
        self.tests_connected = defer.Deferred()
        self.tests_login_failed = defer.Deferred()
        self.master_perspective = None
        orig_got_persp = self.bf.gotPerspective
        orig_failed_get_persp = self.bf.failedToGetPerspective

        def gotPerspective(persp):
            orig_got_persp(persp)
            self.master_perspective = persp
            self.tests_connected.callback(persp)
            persp.broker.notifyOnDisconnect(
                lambda: self.tests_disconnected.callback(None))

        def failedToGetPerspective(why, broker):
            orig_failed_get_persp(why, broker)
            self.tests_login_failed.callback((why, broker))

        self.bf.gotPerspective = gotPerspective
        self.bf.failedToGetPerspective = failedToGetPerspective


class TestWorkerConnection(unittest.TestCase, TestReactorMixin):

    """
    Test handling of connections from real worker code

    This is meant primarily to test the worker itself.

    @ivar master: fake build master
    @ivar pbmanager: L{PBManager} instance
    @ivar botmaster: L{BotMaster} instance
    @ivar buildworker: L{MasterSideWorker} instance
    @ivar port: actual TCP port of the master PB service (fixed after call to
                ``addMasterSideWorker``)
    """

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantMq=True, wantData=True,
                                             wantDb=True)
        # set the worker port to a loopback address with unspecified
        # port
        self.pbmanager = self.master.pbmanager = pbmanager.PBManager()
        self.pbmanager.setServiceParent(self.master)

        # remove the fakeServiceParent from fake service hierarchy, and replace
        # by a real one
        yield self.master.workers.disownServiceParent()
        self.workers = self.master.workers = workermanager.WorkerManager(
            self.master)
        self.workers.setServiceParent(self.master)

        self.botmaster = botmaster.BotMaster()
        self.botmaster.setServiceParent(self.master)

        self.master.status = master.Status()
        self.master.status.setServiceParent(self.master)
        self.master.botmaster = self.botmaster
        self.master.data.updates.workerConfigured = lambda *a, **k: None
        yield self.master.startService()

        self.buildworker = None
        self.port = None
        self.workerworker = None
        self._detach_deferreds = []

        # patch in our FakeBuilder for the regular Builder class
        self.patch(botmaster, 'Builder', FakeBuilder)

        self.client_connection_string_tpl = r"tcp:host=127.0.0.1:port={port}"

        self.tmpdirs = set()

    def tearDown(self):
        for tmp in self.tmpdirs:
            if os.path.exists(tmp):
                shutil.rmtree(tmp)
        deferreds = self._detach_deferreds + [
            self.pbmanager.stopService(),
            self.botmaster.stopService(),
            self.workers.stopService(),
        ]

        # if the worker is still attached, wait for it to detach, too
        if self.buildworker and self.buildworker.detach_d:
            deferreds.append(self.buildworker.detach_d)

        return defer.gatherResults(deferreds)

    @defer.inlineCallbacks
    def addMasterSideWorker(self,
                            connection_string=r"tcp:{port}:interface=127.0.0.1".format(
                                port=DEFAULT_PORT),
                            name="testworker", password="pw",
                            update_port=True,
                            **kwargs):
        """
        Create a master-side worker instance and add it to the BotMaster

        @param **kwargs: arguments to pass to the L{Worker} constructor.
        """
        self.buildworker = MasterSideWorker(name, password, **kwargs)

        # reconfig the master to get it set up
        new_config = self.master.config
        new_config.protocols = {"pb": {"port": connection_string}}
        new_config.workers = [self.buildworker]
        new_config.builders = [config.BuilderConfig(
            name='bldr',
            workername='testworker', factory=factory.BuildFactory())]

        yield self.botmaster.reconfigServiceWithBuildbotConfig(new_config)
        yield self.workers.reconfigServiceWithBuildbotConfig(new_config)

        if update_port:
            # as part of the reconfig, the worker registered with the
            # pbmanager, so get the port it was assigned
            self.port = self.buildworker.registration.getPBPort()

    def workerSideDisconnect(self, worker):
        """Disconnect from the worker side

        This seems a good way to simulate a broken connection
        """
        worker.bf.disconnect()

    def addWorker(self, connection_string_tpl=r"tcp:host=127.0.0.1:port={port}",
                  password="pw", name="testworker", keepalive=None):
        """Add a true Worker object to the services."""
        wdir = tempfile.mkdtemp()
        self.tmpdirs.add(wdir)
        return TestingWorker(None, None, name, password, wdir, keepalive,
                             connection_string=connection_string_tpl.format(port=self.port))

    @defer.inlineCallbacks
    def test_connect_disconnect(self):
        self.addMasterSideWorker()

        def could_not_connect():
            self.fail("Worker never got connected to master")

        timeout = reactor.callLater(10, could_not_connect)
        worker = self.addWorker()
        yield worker.startService()
        yield worker.tests_connected

        timeout.cancel()
        self.assertTrue('bldr' in worker.bot.builders)
        yield worker.stopService()
        yield worker.tests_disconnected

    @defer.inlineCallbacks
    def test_reconnect_network(self):
        self.addMasterSideWorker()

        def could_not_connect():
            self.fail("Worker did not reconnect in time to master")

        worker = self.addWorker(r"tcp:host=127.0.0.1:port={port}")
        yield worker.startService()
        yield worker.tests_connected

        self.assertTrue('bldr' in worker.bot.builders)

        timeout = reactor.callLater(10, could_not_connect)
        self.workerSideDisconnect(worker)
        yield worker.tests_connected

        timeout.cancel()
        yield worker.stopService()
        yield worker.tests_disconnected

    @defer.inlineCallbacks
    def test_applicative_reconnection(self):
        """Test reconnection on PB errors.

        The worker starts with a password that the master does not accept
        at first, and then the master gets reconfigured to accept it.
        """
        self.addMasterSideWorker()
        worker = self.addWorker(password="pw2")
        yield worker.startService()
        why, broker = yield worker.tests_login_failed
        self.assertEqual(1, len(self.flushLoggedErrors(UnauthorizedLogin)))

        def could_not_connect():
            self.fail("Worker did not reconnect in time to master")

        # we have two reasons to call that again:
        # - we really need to instantiate a new one master-side worker,
        #   just changing its password has it simply ignored
        # - we need to fix the port
        yield self.addMasterSideWorker(
            password='pw2',
            update_port=False,  # don't know why, but it'd fail
            connection_string=r"tcp:{port}:interface=127.0.0.1".format(port=self.port))
        timeout = reactor.callLater(10, could_not_connect)
        yield worker.tests_connected

        timeout.cancel()
        self.assertTrue('bldr' in worker.bot.builders)
        yield worker.stopService()
        yield worker.tests_disconnected

    @defer.inlineCallbacks
    def test_pb_keepalive(self):
        """Test applicative (PB) keepalives.

        This works by patching the master to callback a deferred on which the
        test waits.
        """
        def perspective_keepalive(Connection_self):
            waiter = worker.keepalive_waiter
            if waiter is not None:
                waiter.callback(time.time())
        from buildbot.worker.protocols.pb import Connection
        self.patch(Connection, 'perspective_keepalive', perspective_keepalive)

        self.addMasterSideWorker()
        # short keepalive to make the test bearable to run
        worker = self.addWorker(keepalive=0.1)
        worker.keepalive_waiter = defer.Deferred()

        yield worker.startService()
        yield worker.tests_connected
        first = yield worker.keepalive_waiter
        yield worker.bf.currentKeepaliveWaiter

        worker.keepalive_waiter = defer.Deferred()

        second = yield worker.keepalive_waiter
        # avoid errors if a third gets fired
        worker.keepalive_waiter = None
        yield worker.bf.currentKeepaliveWaiter

        self.assertGreater(second, first)
        self.assertLess(second, first + 1)  # seems safe enough

        yield worker.stopService()
        yield worker.tests_disconnected
