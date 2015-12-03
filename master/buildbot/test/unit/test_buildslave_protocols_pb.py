# This file is part of Buildbot. Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

import mock

from buildbot.buildslave.protocols import base
from buildbot.buildslave.protocols import pb
from buildbot.test.fake import fakemaster
from buildbot.test.util import protocols as util_protocols
from twisted.internet import defer
from twisted.spread import pb as twisted_pb
from twisted.trial import unittest


class TestListener(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master()

    def makeListener(self):
        listener = pb.Listener()
        listener.setServiceParent(self.master)
        return listener

    def test_constructor(self):
        listener = self.makeListener()
        self.assertEqual(listener.master, self.master)
        self.assertEqual(listener._registrations, {})

    @defer.inlineCallbacks
    def test_updateRegistration_simple(self):
        listener = self.makeListener()
        reg = yield listener.updateRegistration('example', 'pass', 'tcp:1234')
        self.assertEqual(self.master.pbmanager._registrations,
                         [('tcp:1234', 'example', 'pass')])
        self.assertEqual(listener._registrations['example'], ('pass', 'tcp:1234', reg))

    @defer.inlineCallbacks
    def test_updateRegistration_pass_changed(self):
        listener = self.makeListener()
        listener.updateRegistration('example', 'pass', 'tcp:1234')
        reg1 = yield listener.updateRegistration('example', 'pass1', 'tcp:1234')
        self.assertEqual(listener._registrations['example'], ('pass1', 'tcp:1234', reg1))
        self.assertEqual(self.master.pbmanager._unregistrations, [('tcp:1234', 'example')])

    @defer.inlineCallbacks
    def test_updateRegistration_port_changed(self):
        listener = self.makeListener()
        listener.updateRegistration('example', 'pass', 'tcp:1234')
        reg1 = yield listener.updateRegistration('example', 'pass', 'tcp:4321')
        self.assertEqual(listener._registrations['example'], ('pass', 'tcp:4321', reg1))
        self.assertEqual(self.master.pbmanager._unregistrations, [('tcp:1234', 'example')])

    @defer.inlineCallbacks
    def test_getPerspective(self):
        listener = self.makeListener()
        buildslave = mock.Mock()
        buildslave.slavename = 'test'
        mind = mock.Mock()

        listener.updateRegistration('example', 'pass', 'tcp:1234')
        self.master.buildslaves.register(buildslave)
        conn = yield listener._getPerspective(mind, buildslave.slavename)

        mind.broker.transport.setTcpKeepAlive.assert_called_with(1)
        self.assertIsInstance(conn, pb.Connection)


class TestConnectionApi(util_protocols.ConnectionInterfaceTest,
                        unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.conn = pb.Connection(self.master, mock.Mock(), mock.Mock())


class TestConnection(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master()
        self.mind = mock.Mock()
        self.buildslave = mock.Mock()

    def test_constructor(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)

        self.assertEqual(conn.mind, self.mind)
        self.assertEqual(conn.master, self.master)
        self.assertEqual(conn.buildslave, self.buildslave)

    @defer.inlineCallbacks
    def test_attached(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        att = yield conn.attached(self.mind)

        self.assertNotEqual(conn.keepalive_timer, None)
        self.buildslave.attached.assert_called_with(conn)
        self.assertEqual(att, conn)

        conn.detached(self.mind)

    def test_detached(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        conn.attached(self.mind)
        conn.detached(self.mind)

        self.assertEqual(conn.keepalive_timer, None)
        self.assertEqual(conn.mind, None)

    def test_loseConnection(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        conn.loseConnection()

        self.assertEqual(conn.keepalive_timer, None)
        conn.mind.broker.transport.loseConnection.assert_called_with()

    def test_remotePrint(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        conn.remotePrint(message='test')
        conn.mind.callRemote.assert_called_with('print', message='test')

    @defer.inlineCallbacks
    def test_remoteGetSlaveInfo(self):
        def side_effect(*args, **kwargs):
            if 'getSlaveInfo' in args:
                return defer.succeed({'info': 'test'})
            if 'getCommands' in args:
                return defer.succeed({'x': 1, 'y': 2})
            if 'getVersion' in args:
                return defer.succeed('TheVersion')

        self.mind.callRemote.side_effect = side_effect
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        info = yield conn.remoteGetSlaveInfo()

        r = {'info': 'test', 'slave_commands': {'y': 2, 'x': 1}, 'version': 'TheVersion'}
        self.assertEqual(info, r)
        calls = [mock.call('getSlaveInfo'), mock.call('getCommands'), mock.call('getVersion')]
        self.mind.callRemote.assert_has_calls(calls)

    @defer.inlineCallbacks
    def test_remoteGetSlaveInfo_getSlaveInfo_fails(self):
        def side_effect(*args, **kwargs):
            if 'getSlaveInfo' in args:
                return defer.fail(twisted_pb.NoSuchMethod())
            if 'getCommands' in args:
                return defer.succeed({'x': 1, 'y': 2})
            if 'getVersion' in args:
                return defer.succeed('TheVersion')

        self.mind.callRemote.side_effect = side_effect
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        info = yield conn.remoteGetSlaveInfo()

        r = {'slave_commands': {'y': 2, 'x': 1}, 'version': 'TheVersion'}
        self.assertEqual(info, r)
        calls = [mock.call('getSlaveInfo'), mock.call('getCommands'), mock.call('getVersion')]
        self.mind.callRemote.assert_has_calls(calls)

    @defer.inlineCallbacks
    def test_remoteSetBuilderList(self):
        builders = ['builder1', 'builder2']
        self.mind.callRemote.return_value = defer.succeed(builders)
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        r = yield conn.remoteSetBuilderList(builders)

        self.assertEqual(r, builders)
        self.assertEqual(conn.builders, builders)
        self.mind.callRemote.assert_called_with('setBuilderList', builders)

    def test_remoteStartCommand(self):
        builders = ['builder']
        ret_val = {'builder': mock.Mock()}
        self.mind.callRemote.return_value = defer.succeed(ret_val)
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        conn.remoteSetBuilderList(builders)

        RCInstance, builder_name, commandID = base.RemoteCommandImpl(), "builder", None
        remote_command, args = "command", {"args": 'args'}

        conn.remoteStartCommand(RCInstance, builder_name, commandID, remote_command, args)

        callargs = ret_val['builder'].callRemote.call_args_list[0][0]
        callargs_without_rc = (callargs[0], callargs[2], callargs[3], callargs[4])
        self.assertEqual(callargs_without_rc, ('startCommand',
                                               commandID, remote_command, args))
        self.assertIsInstance(callargs[1], pb.RemoteCommand)
        self.assertEqual(callargs[1].impl, RCInstance)

    def test_doKeepalive(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        conn.doKeepalive()

        self.mind.callRemote.assert_called_with('print', message="keepalive")

    def test_remoteShutdown(self):
        self.mind.callRemote.return_value = defer.succeed(None)
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        # note that we do not test the "old way", as it is now *very* old.
        conn.remoteShutdown()

        self.mind.callRemote.assert_called_with('shutdown')

    def test_remoteStartBuild(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        builders = {'builder': mock.Mock()}
        self.mind.callRemote.return_value = defer.succeed(builders)
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        conn.remoteSetBuilderList(builders)

        conn.remoteStartBuild('builder')

        builders['builder'].callRemote.assert_called_with('startBuild')

    def test_startStopKeepaliveTimer(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)

        conn.startKeepaliveTimer()
        self.assertNotEqual(conn.keepalive_timer, None)

        conn.stopKeepaliveTimer()
        self.assertEqual(conn.keepalive_timer, None)

    def test_perspective_shutdown(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        conn.perspective_shutdown()

        conn.buildslave.shutdownRequested.assert_called_with()
        conn.buildslave.messageReceivedFromSlave.assert_called_with()

    def test_perspective_keepalive(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        conn.perspective_keepalive()

        conn.buildslave.messageReceivedFromSlave.assert_called_with()
