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

import os
import stat

from parameterized import parameterized

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process import remotecommand
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util import protocols as util_protocols
from buildbot.worker.protocols import base
from buildbot.worker.protocols import msgpack


class TestListener(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self)

    def test_constructor(self):
        listener = msgpack.Listener(self.master)
        self.assertEqual(listener.master, self.master)
        self.assertEqual(listener._registrations, {})

    @defer.inlineCallbacks
    def test_update_registration_simple(self):
        listener = msgpack.Listener(self.master)
        reg = yield listener.updateRegistration('example', 'pass', 'tcp:1234')
        self.assertEqual(self.master.msgmanager._registrations, [('tcp:1234', 'example', 'pass')])
        self.assertEqual(listener._registrations['example'], ('pass', 'tcp:1234', reg))

    @defer.inlineCallbacks
    def test_update_registration_pass_changed(self):
        listener = msgpack.Listener(self.master)
        listener.updateRegistration('example', 'pass', 'tcp:1234')
        reg1 = yield listener.updateRegistration('example', 'pass1', 'tcp:1234')
        self.assertEqual(listener._registrations['example'], ('pass1', 'tcp:1234', reg1))
        self.assertEqual(self.master.msgmanager._unregistrations, [('tcp:1234', 'example')])

    @defer.inlineCallbacks
    def test_update_registration_port_changed(self):
        listener = msgpack.Listener(self.master)
        listener.updateRegistration('example', 'pass', 'tcp:1234')
        reg1 = yield listener.updateRegistration('example', 'pass', 'tcp:4321')
        self.assertEqual(listener._registrations['example'], ('pass', 'tcp:4321', reg1))
        self.assertEqual(self.master.msgmanager._unregistrations, [('tcp:1234', 'example')])

    @defer.inlineCallbacks
    def test_create_connection(self):
        listener = msgpack.Listener(self.master)
        listener.before_connection_setup = mock.Mock()
        worker = mock.Mock()
        worker.workername = 'test'
        protocol = mock.Mock()

        listener.updateRegistration('example', 'pass', 'tcp:1234')
        self.master.workers.register(worker)
        conn = yield listener._create_connection(protocol, worker.workername)

        listener.before_connection_setup.assert_called_once_with(protocol, worker.workername)
        self.assertIsInstance(conn, msgpack.Connection)


class TestConnectionApi(util_protocols.ConnectionInterfaceTest,
                        TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self)
        self.conn = msgpack.Connection(self.master, mock.Mock(), mock.Mock())


class TestConnection(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setup_test_reactor()
        self.master = fakemaster.make_master(self)
        self.protocol = mock.Mock()
        self.worker = mock.Mock()
        self.worker.workername = 'test_worker'
        self.conn = msgpack.Connection(self.master, self.worker, self.protocol)

    def test_constructor(self):
        self.assertEqual(self.conn.protocol, self.protocol)
        self.assertEqual(self.conn.master, self.master)
        self.assertEqual(self.conn.worker, self.worker)

    @defer.inlineCallbacks
    def test_attached(self):
        self.conn.attached(self.protocol)
        self.worker.attached.assert_called_with(self.conn)

        self.reactor.pump([10] * 361)
        self.protocol.get_message_result.assert_called_once_with({'op': 'keepalive'})

        self.conn.detached(self.protocol)
        yield self.conn.waitShutdown()

    @defer.inlineCallbacks
    def test_detached(self):
        self.conn.attached(self.protocol)
        self.conn.detached(self.protocol)

        self.assertEqual(self.conn.keepalive_timer, None)
        self.assertEqual(self.conn.protocol, None)
        yield self.conn.waitShutdown()

    def test_lose_connection(self):
        self.conn.loseConnection()

        self.assertEqual(self.conn.keepalive_timer, None)
        self.protocol.transport.abortConnection.assert_called()

    def test_do_keepalive(self):
        self.conn._do_keepalive()
        self.protocol.get_message_result.assert_called_once_with({'op': 'keepalive'})

    @defer.inlineCallbacks
    def test_start_stop_keepalive_timer(self):
        self.conn.startKeepaliveTimer()

        self.protocol.get_message_result.assert_not_called()

        self.reactor.pump([10] * 361)
        expected_call = [
            mock.call({'op': 'keepalive'}),
        ]
        self.assertEqual(self.protocol.get_message_result.call_args_list, expected_call)

        self.reactor.pump([10] * 361)
        expected_calls = [
            mock.call({'op': 'keepalive'}),
            mock.call({'op': 'keepalive'}),
        ]
        self.assertEqual(self.protocol.get_message_result.call_args_list, expected_calls)

        self.conn.stopKeepaliveTimer()

        self.reactor.pump([10] * 361)
        expected_calls = [
            mock.call({'op': 'keepalive'}),
            mock.call({'op': 'keepalive'}),
        ]
        self.assertEqual(self.protocol.get_message_result.call_args_list, expected_calls)

        yield self.conn.waitShutdown()

    @defer.inlineCallbacks
    def test_remote_keepalive(self):
        yield self.conn.remoteKeepalive()
        self.protocol.get_message_result.assert_called_once_with({'op': 'keepalive'})

    @defer.inlineCallbacks
    def test_remote_print(self):
        yield self.conn.remotePrint(message='test')
        self.protocol.get_message_result.assert_called_once_with({'op': 'print',
                                                                  'message': 'test'})

    @defer.inlineCallbacks
    def test_remote_get_worker_info(self):
        self.protocol.get_message_result.return_value = defer.succeed({'system': 'posix'})
        result = yield self.conn.remoteGetWorkerInfo()

        self.protocol.get_message_result.assert_called_once_with({'op': 'get_worker_info'})
        self.assertEqual(result, {'system': 'posix'})

    def set_up_set_builder_list(self, builders, delete_leftover_dirs=True):
        self.protocol.command_id_to_command_map = {}

        def get_message_result(*args):
            d = defer.Deferred()
            self.d_get_message_result = d
            return d

        self.protocol.get_message_result.side_effect = get_message_result
        self.conn.info = {'basedir': 'testdir'}
        self.conn.info['delete_leftover_dirs'] = delete_leftover_dirs
        self.conn.path_module = os.path
        d = self.conn.remoteSetBuilderList(builders)
        return d

    def check_message_send_response(self, command_name, args, update_msg):
        command_id = remotecommand.RemoteCommand.get_last_generated_command_id()
        self.protocol.get_message_result.assert_called_once_with({'op': 'start_command',
                                                                  'command_id': command_id,
                                                                  'command_name': command_name,
                                                                  'args': args})
        self.protocol.get_message_result.reset_mock()
        self.d_get_message_result.callback(None)

        remote_command = self.protocol.command_id_to_command_map[command_id]
        remote_command.remote_update_msgpack(update_msg)
        remote_command.remote_complete(None)

    def check_message_set_worker_settings(self):
        newline_re = r'(\r\n|\r(?=.)|\033\[u|\033\[[0-9]+;[0-9]+[Hf]|\033\[2J|\x08+)'
        self.protocol.get_message_result.assert_called_once_with({
            'op': 'set_worker_settings',
            'args': {
                'newline_re': newline_re,
                'max_line_length': 4096,
                'buffer_timeout': 5,
                'buffer_size': 64 * 1024
            }
        })
        self.protocol.get_message_result.reset_mock()
        self.d_get_message_result.callback(None)

    @defer.inlineCallbacks
    def test_remote_set_builder_list_no_rmdir(self):
        d = self.set_up_set_builder_list([('builder1', 'test_dir1'), ('builder2', 'test_dir2')])
        self.check_message_set_worker_settings()

        self.check_message_send_response('listdir', {'path': 'testdir'},
                                         [('files', ['dir1', 'dir2', 'dir3']), ('rc', 0)])

        path = os.path.join('testdir', 'dir1')
        self.check_message_send_response('stat', {'path': path}, [('stat', (1,)), ('rc', 0)])

        path = os.path.join('testdir', 'dir2')
        self.check_message_send_response('stat', {'path': path}, [('stat', (1,)), ('rc', 0)])

        path = os.path.join('testdir', 'dir3')
        self.check_message_send_response('stat', {'path': path}, [('stat', (1,)), ('rc', 0)])

        paths = [os.path.join('testdir', 'info'), os.path.join('testdir', 'test_dir1'),
                 os.path.join('testdir', 'test_dir2')]
        self.check_message_send_response('mkdir', {'paths': paths}, [('rc', 0)])

        r = yield d
        self.assertEqual(r, ['builder1', 'builder2'])
        self.protocol.get_message_result.assert_not_called()

    @defer.inlineCallbacks
    def test_remote_set_builder_list_do_rmdir(self):
        d = self.set_up_set_builder_list([('builder1', 'test_dir1'), ('builder2', 'test_dir2')])
        self.check_message_set_worker_settings()

        self.check_message_send_response('listdir', {'path': 'testdir'},
                                         [('files', ['dir1', 'dir2', 'dir3']), ('rc', 0)])

        path = os.path.join('testdir', 'dir1')
        self.check_message_send_response('stat', {'path': path},
                                         [('stat', (stat.S_IFDIR,)), ('rc', 0)])

        path = os.path.join('testdir', 'dir2')
        self.check_message_send_response('stat', {'path': path},
                                         [('stat', (stat.S_IFDIR,)), ('rc', 0)])

        path = os.path.join('testdir', 'dir3')
        self.check_message_send_response('stat', {'path': path},
                                         [('stat', (stat.S_IFDIR,)), ('rc', 0)])

        paths = [os.path.join('testdir', 'dir1'), os.path.join('testdir', 'dir2'),
                 os.path.join('testdir', 'dir3')]
        self.check_message_send_response('rmdir', {'paths': paths}, [('rc', 0)])

        paths = [os.path.join('testdir', 'info'), os.path.join('testdir', 'test_dir1'),
                 os.path.join('testdir', 'test_dir2')]
        self.check_message_send_response('mkdir', {'paths': paths}, [('rc', 0)])

        r = yield d
        self.assertEqual(r, ['builder1', 'builder2'])
        self.protocol.get_message_result.assert_not_called()

    @defer.inlineCallbacks
    def test_remote_set_builder_list_no_rmdir_leave_leftover_dirs(self):
        d = self.set_up_set_builder_list([('builder1', 'test_dir1'), ('builder2', 'test_dir2')],
                                         delete_leftover_dirs=False)
        self.check_message_set_worker_settings()

        self.check_message_send_response('listdir', {'path': 'testdir'},
                                         [('files', ['dir1', 'dir2', 'dir3']), ('rc', 0)])

        paths = [os.path.join('testdir', 'info'), os.path.join('testdir', 'test_dir1'),
                 os.path.join('testdir', 'test_dir2')]
        self.check_message_send_response('mkdir', {'paths': paths}, [('rc', 0)])

        r = yield d
        self.assertEqual(r, ['builder1', 'builder2'])
        self.protocol.get_message_result.assert_not_called()

    @defer.inlineCallbacks
    def test_remote_set_builder_list_no_mkdir_from_files(self):
        d = self.set_up_set_builder_list([('builder1', 'test_dir1'), ('builder2', 'test_dir2')])
        self.check_message_set_worker_settings()

        self.check_message_send_response('listdir', {'path': 'testdir'},
                                         [('files', ['dir1', 'test_dir2']), ('rc', 0)])

        path = os.path.join('testdir', 'dir1')
        self.check_message_send_response('stat', {'path': path}, [('stat', (1,)), ('rc', 0)])

        paths = [os.path.join('testdir', 'info'), os.path.join('testdir', 'test_dir1')]
        self.check_message_send_response('mkdir', {'paths': paths}, [('rc', 0)])

        r = yield d
        self.assertEqual(r, ['builder1', 'builder2'])
        self.protocol.get_message_result.assert_not_called()

    @defer.inlineCallbacks
    def test_remote_set_builder_list_no_mkdir(self):
        d = self.set_up_set_builder_list([('builder1', 'test_dir1'), ('builder2', 'test_dir2')])
        self.check_message_set_worker_settings()

        self.check_message_send_response('listdir', {'path': 'testdir'},
                                         [('files', ['test_dir1', 'test_dir2', 'info']), ('rc', 0)])

        r = yield d
        self.assertEqual(r, ['builder1', 'builder2'])
        self.protocol.get_message_result.assert_not_called()

    @defer.inlineCallbacks
    def test_remote_set_builder_list_key_is_missing(self):
        d = self.set_up_set_builder_list([('builder1', 'test_dir1'), ('builder2', 'test_dir2')])
        self.check_message_set_worker_settings()

        self.check_message_send_response('listdir', {'path': 'testdir'},
                                         [('no_key', []), ('rc', 0)])

        with self.assertRaisesRegex(Exception, "Key 'files' is missing."):
            yield d

        self.protocol.get_message_result.assert_not_called()

    @defer.inlineCallbacks
    def test_remote_set_builder_list_key_rc_not_zero(self):
        d = self.set_up_set_builder_list([('builder1', 'test_dir1'), ('builder2', 'test_dir2')])
        self.check_message_set_worker_settings()

        self.check_message_send_response('listdir', {'path': 'testdir'}, [('rc', 123)])

        with self.assertRaisesRegex(Exception, "Error number: 123"):
            yield d

        self.protocol.get_message_result.assert_not_called()

    @parameterized.expand([
        ('want_stdout', 0, False),
        ('want_stdout', 1, True),
        ('want_stderr', 0, False),
        ('want_stderr', 1, True),
        (None, None, None)
    ])
    @defer.inlineCallbacks
    def test_remote_start_command_args_update(self, arg_name, arg_value, expected_value):
        self.protocol.get_message_result.return_value = defer.succeed(None)

        rc_instance = base.RemoteCommandImpl()
        result_command_id_to_command_map = {1: rc_instance}
        self.protocol.command_id_to_command_map = {}
        args = {'args': 'args'}

        if arg_name is not None:
            args[arg_name] = arg_value

        yield self.conn.remoteStartCommand(rc_instance, 'builder', 1, 'command', args)
        expected_args = args.copy()
        if arg_name is not None:
            expected_args[arg_name] = expected_value

        self.assertEqual(result_command_id_to_command_map, self.protocol.command_id_to_command_map)
        self.protocol.get_message_result.assert_called_with({'op': 'start_command',
                                                             'builder_name': 'builder',
                                                             'command_id': 1,
                                                             'command_name': 'command',
                                                             'args': expected_args})

    @defer.inlineCallbacks
    def test_remote_shutdown(self):
        self.protocol.get_message_result.return_value = defer.succeed(None)
        yield self.conn.remoteShutdown()

        self.protocol.get_message_result.assert_called_once_with({'op': 'shutdown'})

    @defer.inlineCallbacks
    def test_remote_interrupt_command(self):
        self.protocol.get_message_result.return_value = defer.succeed(None)
        yield self.conn.remoteInterruptCommand('builder', 1, 'test')

        self.protocol.get_message_result.assert_called_once_with({'op': 'interrupt_command',
                                                                  'builder_name': 'builder',
                                                                  'command_id': 1, 'why': 'test'})

    def test_perspective_keepalive(self):
        self.conn.perspective_keepalive()
        self.conn.worker.messageReceivedFromWorker.assert_called_once_with()

    def test_perspective_shutdown(self):
        self.conn.perspective_shutdown()

        self.conn.worker.shutdownRequested.assert_called_once_with()
        self.conn.worker.messageReceivedFromWorker.assert_called_once_with()
