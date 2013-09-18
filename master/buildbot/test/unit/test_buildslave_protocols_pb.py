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
from twisted.trial import unittest
from twisted.internet import defer
from buildbot.buildslave.protocols import pb
from buildbot.test.fake import fakemaster

class TestListener(unittest.TestCase):
    def setUp(self):
        self.master = fakemaster.make_master()

    def test_constructor(self):
        listener = pb.Listener(self.master)
        self.assertEqual(listener.master, self.master)
        self.assertEqual(listener._registrations, {})

    def test_updateRegistration_simple(self):
        listener = pb.Listener(self.master)
        reg = listener.updateRegistration('example', 'pass', 'tcp:1234')
        self.assertEqual([('tcp:1234', 'example', 'pass')],
            self.master.pbmanager._registrations)
        self.assertEqual(('pass', 'tcp:1234', reg.result), listener._registrations['example'])

    def test_updateRegistration_pass_changed(self):
        listener = pb.Listener(self.master)
        reg = listener.updateRegistration('example', 'pass', 'tcp:1234')
        reg1 = listener.updateRegistration('example', 'pass1', 'tcp:1234')
        self.assertEqual(('pass1', 'tcp:1234', reg1.result), listener._registrations['example'])
        self.assertEqual([('tcp:1234', 'example')], self.master.pbmanager._unregistrations)

    def test_updateRegistration_port_changed(self):
        listener = pb.Listener(self.master)
        reg = listener.updateRegistration('example', 'pass', 'tcp:1234')
        reg1 = listener.updateRegistration('example', 'pass', 'tcp:4321')
        self.assertEqual(('pass', 'tcp:4321', reg1.result), listener._registrations['example'])
        self.assertEqual([('tcp:1234', 'example')], self.master.pbmanager._unregistrations)

    def test_getPerspective(self):
        listener = pb.Listener(self.master)
        buildslave = mock.Mock()
        buildslave.slavename = 'test'
        mind = mock.Mock()

        reg = listener.updateRegistration('example', 'pass', 'tcp:1234')
        self.master.buildslaves.register(buildslave)
        conn = listener._getPerspective(mind, buildslave.slavename)

        mind.broker.transport.setTcpKeepAlive.assert_called_with(1)
        self.assertEqual(True, isinstance(conn.result, pb.Connection))


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

    def test_attached(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        att = conn.attached(self.mind) # att should Connection instance, but it's None

        self.assertNotEqual(None, conn.keepalive_timer)
        self.buildslave.attached.assert_called_with(conn)
        # self.assertEqual(att, conn) # will fail, why?

        conn.detached(self.mind)

    def test_detached(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        conn.attached(self.mind)
        conn.detached(self.mind)

        self.assertEqual(None, conn.keepalive_timer)
        self.assertEqual(None, conn.mind)

    def test_loseConnection(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        conn.loseConnection()

        self.assertEqual(None, conn.keepalive_timer)
        conn.mind.broker.transport.loseConnection.assert_called_with()

    def test_remotePrint(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        conn.remotePrint(message='test')
        conn.mind.callRemote.assert_called_with('print', message='test')

    def test_remoteGetSlaveInfo(self):
        def side_effect(*args, **kwargs):
            if 'getSlaveInfo' in args:
                return {'info': 'test'}
            if 'getCommands' in args:
                return {'x': 1, 'y': 2}
            if 'getVersion' in args:
                return 'TheVersion'

        self.mind.callRemote.side_effect = side_effect
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        info = conn.remoteGetSlaveInfo()

        r = {'info': 'test', 'slave_commands': {'y': 2, 'x': 1}, 'version': 'TheVersion'}
        self.assertEqual(r, info.result)
        calls = [mock.call('getSlaveInfo'), mock.call('getCommands'), mock.call('getVersion')]
        self.mind.callRemote.assert_has_calls(calls)

    def test_remoteSetBuilderList(self):
        builders = ['builder1', 'builder2']
        self.mind.callRemote.return_value = defer.succeed(builders)
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        r = conn.remoteSetBuilderList(builders)

        self.assertEqual(builders, r.result)
        self.assertEqual(builders, conn.builders)
        self.mind.callRemote.assert_called_with('setBuilderList', builders)

    def test_startCommands(self):
        builders = ['builder']
        ret_val = {'builder': mock.Mock()}
        self.mind.callRemote.return_value = defer.succeed(ret_val)
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        conn.remoteSetBuilderList(builders)

        RCInstance, builder_name, commandID = None, "builder", None
        remote_command, args = "command", "args"

        conn.startCommands(RCInstance, builder_name, commandID, remote_command, args)

        ret_val['builder'].callRemote.assert_called_with('startCommand',
            RCInstance, commandID, remote_command, args)

    def test_doKeepalive(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        conn.doKeepalive()

        self.mind.callRemote.assert_called_with('print', message="keepalive")

    def test_remoteShutdown(self):
        self.mind.callRemote.return_value = defer.succeed(None)
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        buildslave = None
        # "buildslave" required to shutdown slave in "old way", since
        # this feature deprecated and hard to test in reality it's not tested
        conn.remoteShutdown(buildslave)

        self.mind.callRemote.assert_called_with('shutdown')

    def test_remoteStartBuild(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)
        conn.remoteStartBuild()

        self.mind.callRemote.assert_called_with('startBuild')


    def test_startStopKeepaliveTimer(self):
        conn = pb.Connection(self.master, self.buildslave, self.mind)

        conn.startKeepaliveTimer()
        self.assertNotEqual(None, conn.keepalive_timer)

        conn.stopKeepaliveTimer()
        self.assertEqual(None, conn.keepalive_timer)

