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

import mock

from twisted.cred import credentials
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.endpoints import clientFromString
from twisted.python import log
from twisted.python import util
from twisted.spread import pb
from twisted.trial import unittest

import buildbot
from buildbot import config
from buildbot import pbmanager
from buildbot import worker
from buildbot.process import botmaster
from buildbot.process import builder
from buildbot.process import factory
from buildbot.status import master
from buildbot.test.fake import fakemaster
from buildbot.test.util.misc import TestReactorMixin
from buildbot.util.eventual import eventually
from buildbot.worker import manager as workermanager

PKI_DIR = util.sibpath(__file__, 'pki')


class FakeWorkerForBuilder(pb.Referenceable):

    """
    Fake worker-side WorkerForBuilder object
    """


class FakeWorkerWorker(pb.Referenceable):

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
        log.msg("WORKER-SIDE: remote_print(%r)" % (message,))

    def remote_getWorkerInfo(self):
        return {
            'info': 'here',
            'worker_commands': {
                'x': 1,
            },
            'numcpus': 1,
            'none': None,
            'os_release': b'\xe3\x83\x86\xe3\x82\xb9\xe3\x83\x88'.decode(),
            b'\xe3\x83\xaa\xe3\x83\xaa\xe3\x83\xbc\xe3\x82\xb9\xe3'
            b'\x83\x86\xe3\x82\xb9\xe3\x83\x88'.decode(): b'\xe3\x83\x86\xe3\x82\xb9\xe3\x83\x88'.decode(),
        }

    def remote_getVersion(self):
        return buildbot.version

    def remote_getCommands(self):
        return {'x': 1}

    def remote_setBuilderList(self, builder_info):
        builder_names = [n for n, dir in builder_info]
        slbuilders = [FakeWorkerForBuilder() for n in builder_names]
        eventually(self.callWhenBuilderListSet)
        return dict(zip(builder_names, slbuilders))


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


class MyWorker(worker.Worker):

    def attached(self, conn):
        self.detach_d = defer.Deferred()
        return super().attached(conn)

    def detached(self):
        super().detached()
        self.detach_d, d = None, self.detach_d
        d.callback(None)


class TestWorkerComm(unittest.TestCase, TestReactorMixin):

    """
    Test handling of connections from workers as integrated with
     - Twisted Spread
     - real TCP connections.
     - PBManager

    @ivar master: fake build master
    @ivar pbamanger: L{PBManager} instance
    @ivar botmaster: L{BotMaster} instance
    @ivar worker: master-side L{Worker} instance
    @ivar workerworker: worker-side L{FakeWorkerWorker} instance
    @ivar port: TCP port to connect to
    @ivar server_connection_string: description string for the server endpoint
    @ivar client_connection_string_tpl: description string template for the client
                                endpoint (expects to passed 'port')
    @ivar endpoint: endpoint controlling the outbound connection
                    from worker to master
    """

    @defer.inlineCallbacks
    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantMq=True, wantData=True,
                                             wantDb=True)

        # set the worker port to a loopback address with unspecified
        # port
        self.pbmanager = self.master.pbmanager = pbmanager.PBManager()
        yield self.pbmanager.setServiceParent(self.master)

        # remove the fakeServiceParent from fake service hierarchy, and replace
        # by a real one
        yield self.master.workers.disownServiceParent()
        self.workers = self.master.workers = workermanager.WorkerManager(
            self.master)
        yield self.workers.setServiceParent(self.master)

        self.botmaster = botmaster.BotMaster()
        yield self.botmaster.setServiceParent(self.master)

        self.master.status = master.Status()
        yield self.master.status.setServiceParent(self.master)
        self.master.botmaster = self.botmaster
        self.master.data.updates.workerConfigured = lambda *a, **k: None
        yield self.master.startService()

        self.buildworker = None
        self.port = None
        self.workerworker = None
        self.endpoint = None
        self.broker = None
        self._detach_deferreds = []

        # patch in our FakeBuilder for the regular Builder class
        self.patch(botmaster, 'Builder', FakeBuilder)

        self.server_connection_string = "tcp:0:interface=127.0.0.1"
        self.client_connection_string_tpl = "tcp:host=127.0.0.1:port={port}"

    def tearDown(self):
        if self.broker:
            del self.broker
        if self.endpoint:
            del self.endpoint
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
    def addWorker(self, **kwargs):
        """
        Create a master-side worker instance and add it to the BotMaster

        @param **kwargs: arguments to pass to the L{Worker} constructor.
        """
        self.buildworker = MyWorker("testworker", "pw", **kwargs)

        # reconfig the master to get it set up
        new_config = self.master.config
        new_config.protocols = {"pb": {"port": self.server_connection_string}}
        new_config.workers = [self.buildworker]
        new_config.builders = [config.BuilderConfig(
            name='bldr',
            workername='testworker', factory=factory.BuildFactory())]

        yield self.botmaster.reconfigServiceWithBuildbotConfig(new_config)
        yield self.workers.reconfigServiceWithBuildbotConfig(new_config)

        # as part of the reconfig, the worker registered with the pbmanager, so
        # get the port it was assigned
        self.port = self.buildworker.registration.getPBPort()

    def connectWorker(self, waitForBuilderList=True):
        """
        Connect a worker the master via PB

        @param waitForBuilderList: don't return until the setBuilderList has
        been called
        @returns: L{FakeWorkerWorker} and a Deferred that will fire when it
        is detached; via deferred
        """
        factory = pb.PBClientFactory()
        creds = credentials.UsernamePassword(b"testworker", b"pw")
        setBuilderList_d = defer.Deferred()
        workerworker = FakeWorkerWorker(
            lambda: setBuilderList_d.callback(None))

        login_d = factory.login(creds, workerworker)

        @login_d.addCallback
        def logged_in(persp):
            workerworker.setMasterPerspective(persp)

            # set up to hear when the worker side disconnects
            workerworker.detach_d = defer.Deferred()
            persp.broker.notifyOnDisconnect(
                lambda: workerworker.detach_d.callback(None))
            self._detach_deferreds.append(workerworker.detach_d)

            return workerworker

        self.endpoint = clientFromString(
                reactor, self.client_connection_string_tpl.format(port=self.port))
        connected_d = self.endpoint.connect(factory)

        dlist = [connected_d, login_d]
        if waitForBuilderList:
            dlist.append(setBuilderList_d)

        d = defer.DeferredList(dlist,
                               consumeErrors=True, fireOnOneErrback=True)
        d.addCallback(lambda _: workerworker)
        return d

    def workerSideDisconnect(self, worker):
        """Disconnect from the worker side"""
        worker.master_persp.broker.transport.loseConnection()

    @defer.inlineCallbacks
    def test_connect_disconnect(self):
        """Test a single worker connecting and disconnecting."""
        yield self.addWorker()

        # connect
        worker = yield self.connectWorker()

        # disconnect
        self.workerSideDisconnect(worker)

        # wait for the resulting detach
        yield worker.waitForDetach()

    @defer.inlineCallbacks
    def test_tls_connect_disconnect(self):
        """Test with TLS or SSL endpoint.

        According to the deprecation note for the SSL client endpoint,
        the TLS endpoint is supported from Twistd 16.0.

        TODO add certificate verification (also will require some conditionals
        on various versions, including PyOpenSSL, service_identity. The CA used
        to generate the testing cert is in ``PKI_DIR/ca``
        """
        def escape_colon(path):
            # on windows we can't have \ as it serves as the escape character for :
            return path.replace('\\', '/').replace(':', '\\:')
        self.server_connection_string = (
            "ssl:port=0:certKey={pub}:privateKey={priv}:" +
            "interface=127.0.0.1").format(
                pub=escape_colon(os.path.join(PKI_DIR, '127.0.0.1.crt')),
                priv=escape_colon(os.path.join(PKI_DIR, '127.0.0.1.key')))
        self.client_connection_string_tpl = "ssl:host=127.0.0.1:port={port}"

        yield self.addWorker()

        # connect
        worker = yield self.connectWorker()

        # disconnect
        self.workerSideDisconnect(worker)

        # wait for the resulting detach
        yield worker.waitForDetach()

    @defer.inlineCallbacks
    def test_worker_info(self):
        yield self.addWorker()
        worker = yield self.connectWorker()
        props = self.buildworker.worker_status.info
        # check worker info passing
        self.assertEqual(props.getProperty("info"),
                         "here")
        # check worker info passing with UTF-8
        self.assertEqual(props.getProperty("os_release"),
                         b'\xe3\x83\x86\xe3\x82\xb9\xe3\x83\x88'.decode())
        self.assertEqual(props.getProperty(b'\xe3\x83\xaa\xe3\x83\xaa\xe3\x83\xbc\xe3\x82'
                                           b'\xb9\xe3\x83\x86\xe3\x82\xb9\xe3\x83\x88'.decode()),
                         b'\xe3\x83\x86\xe3\x82\xb9\xe3\x83\x88'.decode())
        self.assertEqual(props.getProperty("none"), None)
        self.assertEqual(props.getProperty("numcpus"), 1)

        self.workerSideDisconnect(worker)
        yield worker.waitForDetach()

    @defer.inlineCallbacks
    def _test_duplicate_worker(self):
        yield self.addWorker()

        # connect first worker
        worker1 = yield self.connectWorker()

        # connect second worker; this should fail
        try:
            yield self.connectWorker(waitForBuilderList=False)
            connect_failed = False
        except Exception:
            connect_failed = True
        self.assertTrue(connect_failed)

        # disconnect both and wait for that to percolate
        self.workerSideDisconnect(worker1)

        yield worker1.waitForDetach()

        # flush the exception logged for this on the master
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    @defer.inlineCallbacks
    def _test_duplicate_worker_old_dead(self):
        yield self.addWorker()

        # connect first worker
        worker1 = yield self.connectWorker()

        # monkeypatch that worker to fail with PBConnectionLost when its
        # remote_print method is called
        def remote_print(message):
            worker1.master_persp.broker.transport.loseConnection()
            raise pb.PBConnectionLost("fake!")
        worker1.remote_print = remote_print

        # connect second worker; this should succeed, and the old worker
        # should be disconnected.
        worker2 = yield self.connectWorker()

        # disconnect both and wait for that to percolate
        self.workerSideDisconnect(worker2)

        yield worker1.waitForDetach()

        # flush the exception logged for this on the worker
        self.assertEqual(len(self.flushLoggedErrors(pb.PBConnectionLost)), 1)
