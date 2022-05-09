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

import base64

import msgpack
from parameterized import parameterized

import mock

from autobahn.websocket.types import ConnectionDeny
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.worker.protocols.manager.msgpack import BuildbotWebSocketServerProtocol
from buildbot.worker.protocols.manager.msgpack import ConnectioLostError
from buildbot.worker.protocols.manager.msgpack import RemoteWorkerError
from buildbot.worker.protocols.manager.msgpack import decode_http_authorization_header
from buildbot.worker.protocols.manager.msgpack import encode_http_authorization_header


class TestHttpAuthorization(unittest.TestCase):

    def test_encode(self):
        result = encode_http_authorization_header(b'name', b'pass')
        self.assertEqual(result, 'Basic bmFtZTpwYXNz')

        result = encode_http_authorization_header(b'name2', b'pass2')
        self.assertEqual(result, 'Basic bmFtZTI6cGFzczI=')

    def test_encode_username_contains_colon(self):
        with self.assertRaises(ValueError):
            encode_http_authorization_header(b'na:me', b'pass')

    def test_decode(self):
        result = decode_http_authorization_header(
            encode_http_authorization_header(b'name', b'pass'))
        self.assertEqual(result, ('name', 'pass'))

        # password can contain a colon
        result = decode_http_authorization_header(
            encode_http_authorization_header(b'name', b'pa:ss'))
        self.assertEqual(result, ('name', 'pa:ss'))

    def test_contains_no__basic(self):
        with self.assertRaises(ValueError):
            decode_http_authorization_header('Test bmFtZTpwYXNzOjI=')

        with self.assertRaises(ValueError):
            decode_http_authorization_header('TestTest bmFtZTpwYXNzOjI=')

    def test_contains_forbidden_character(self):
        with self.assertRaises(ValueError):
            decode_http_authorization_header('Basic test%test')

    def test_credentials_do_not_contain_colon(self):
        value = 'Basic ' + base64.b64encode(b'TestTestTest').decode()
        with self.assertRaises(ValueError):
            decode_http_authorization_header(value)


class TestException(Exception):
    pass


class TestBuildbotWebSocketServerProtocol(unittest.TestCase):
    def setUp(self):
        self.protocol = BuildbotWebSocketServerProtocol()
        self.protocol.sendMessage = mock.Mock()
        self.seq_number = 1

    @defer.inlineCallbacks
    def send_msg_check_response(self, protocol, msg, expected):
        msg = msg.copy()
        msg['seq_number'] = self.seq_number

        expected = expected.copy()
        expected['seq_number'] = self.seq_number
        self.seq_number += 1

        protocol.onMessage(msgpack.packb(msg), True)
        yield protocol._deferwaiter.wait()
        args_tuple = protocol.sendMessage.call_args.args
        result = msgpack.unpackb(args_tuple[0], raw=False)
        self.assertEqual(result, expected)

    def send_msg_get_result(self, msg):
        msg = msg.copy()
        msg['seq_number'] = self.seq_number
        self.seq_number += 1

        self.protocol.onMessage(msgpack.packb(msg), True)

        args_tuple = self.protocol.sendMessage.call_args.args
        return msgpack.unpackb(args_tuple[0], raw=False)['result']

    @defer.inlineCallbacks
    def connect_authenticated_worker(self):
        # worker has to be authenticated before opening the connection
        pfactory = mock.Mock()
        pfactory.connection = mock.Mock()

        self.setup_mock_users({'name': ('pass', pfactory)})

        request = mock.Mock()
        request.headers = {"authorization": 'Basic bmFtZTpwYXNz'}
        request.peer = ''

        yield self.protocol.onConnect(request)
        yield self.protocol.onOpen()

    def setup_mock_users(self, users):
        self.protocol.factory = mock.Mock()
        self.protocol.factory.buildbot_dispatcher = mock.Mock()
        self.protocol.factory.buildbot_dispatcher.users = users

    @parameterized.expand([
        ('update_op', {'seq_number': 1}),
        ('update_seq_number', {'op': 'update'}),
        ('complete_op', {'seq_number': 1}),
        ('complete_seq_number', {'op': 'complete'}),
        ('update_upload_file_write_op', {'seq_number': 1}),
        ('update_upload_file_write_seq_number', {'op': 'update_upload_file_write'}),
        ('update_upload_file_utime_op', {'seq_number': 1}),
        ('update_upload_file_utime_seq_number', {'op': 'update_upload_file_utime'}),
        ('update_upload_file_close_op', {'seq_number': 1}),
        ('update_upload_file_close_seq_number', {'op': 'update_upload_file_close'}),
        ('update_read_file_op', {'seq_number': 1}),
        ('update_read_file_seq_number', {'op': 'update_read_file'}),
        ('update_read_file_close_op', {'seq_number': 1}),
        ('update_read_file_close_seq_number', {'op': 'update_read_file_close'}),
        ('update_upload_directory_unpack_op', {'seq_number': 1}),
        ('update_upload_directory_unpack_seq_number', {'op': 'update_upload_directory_unpack'}),
        ('update_upload_directory_write_op', {'seq_number': 1}),
        ('update_upload_directory_write_seq_number', {'op': 'update_upload_directory_write'}),
    ])
    def test_msg_missing_arg(self, name, msg):
        with mock.patch('twisted.python.log.msg') as mock_log:
            self.protocol.onMessage(msgpack.packb(msg), True)
            mock_log.assert_any_call(f'Invalid message from worker: {msg}')

        # if msg does not have 'sep_number' or 'op', response sendMessage should not be called
        self.protocol.sendMessage.assert_not_called()

    @parameterized.expand([
        ('update', {'op': 'update', 'args': 'args'}),
        ('complete', {'op': 'complete', 'args': 'args'}),
        ('update_upload_file_write', {'op': 'update_upload_file_write', 'args': 'args'}),
        ('update_upload_file_utime', {
            'op': 'update_upload_file_utime',
            'access_time': 1,
            'modified_time': 2
        }),
        ('update_upload_file_close', {'op': 'update_upload_file_close'}),
        ('update_read_file', {'op': 'update_read_file', 'length': 1}),
        ('update_read_file_close', {'op': 'update_read_file_close'}),
        ('update_upload_directory_unpack', {'op': 'update_upload_directory_unpack'}),
        ('upload_directory_write', {'op': 'update_upload_directory_write', 'args': 'args'}),
    ])
    @defer.inlineCallbacks
    def test_missing_command_id(self, command, msg):
        yield self.connect_authenticated_worker()
        expected = {
            'op': 'response',
            'result': '\'message did not contain obligatory "command_id" key\'',
            'is_exception': True
        }
        yield self.send_msg_check_response(self.protocol, msg, expected)

    @parameterized.expand([
        ('update', {'op': 'update', 'args': 'args', 'command_id': 2}, {1: 'remoteCommand'}),
        ('complete', {'op': 'complete', 'args': 'args', 'command_id': 2}, {1: 'remoteCommand'}),
    ])
    @defer.inlineCallbacks
    def test_unknown_command_id(self, command, msg, command_id_to_command_map):
        yield self.connect_authenticated_worker()
        self.protocol.command_id_to_command_map = command_id_to_command_map
        expected = {
            'op': 'response',
            'result': '\'unknown "command_id"\'',
            'is_exception': True
        }
        yield self.send_msg_check_response(self.protocol, msg, expected)

    @parameterized.expand([
        ('update_upload_file_write', {
            'op': 'update_upload_file_write',
            'args': 'args',
            'command_id': 2
        }),
        ('update_upload_directory_unpack', {
            'op': 'update_upload_directory_unpack',
            'command_id': 2
        }),
        ('update_upload_file_close', {
            'op': 'update_upload_file_close',
            'command_id': 2
        }),
        ('update_upload_file_utime', {
            'op': 'update_upload_file_utime',
            'access_time': 1,
            'modified_time': 2,
            'command_id': 2
        }),
        ('update_upload_directory_write', {
            'op': 'update_upload_directory_write',
            'command_id': 2,
            'args': 'args'
        })
    ])
    @defer.inlineCallbacks
    def test_unknown_command_id_writers(self, command, msg):
        yield self.connect_authenticated_worker()
        self.protocol.command_id_to_writer_map = {1: 'writer'}
        expected = {
            'op': 'response',
            'result': '\'unknown "command_id"\'',
            'is_exception': True
        }
        yield self.send_msg_check_response(self.protocol, msg, expected)

    @parameterized.expand([
        ('update', {'op': 'update', 'command_id': 2}),
        ('complete', {'op': 'complete', 'command_id': 2}),
        ('update_upload_file_write', {'op': 'update_upload_file_write', 'command_id': 2}),
        ('update_upload_directory_write', {'op': 'update_upload_directory_write', 'command_id': 1})
    ])
    @defer.inlineCallbacks
    def test_missing_args(self, command, msg):
        yield self.connect_authenticated_worker()
        expected = {
            'op': 'response',
            'result': '\'message did not contain obligatory "args" key\'',
            'is_exception': True
        }
        yield self.send_msg_check_response(self.protocol, msg, expected)

    @parameterized.expand([
        ('update_read_file', {'op': 'update_read_file', 'length': 1, 'command_id': 2}),
        ('update_read_file_close', {'op': 'update_read_file_close', 'command_id': 2})
    ])
    @defer.inlineCallbacks
    def test_unknown_command_id_readers(self, command, msg):
        yield self.connect_authenticated_worker()
        self.protocol.command_id_to_reader_map = {1: 'reader'}
        expected = {
            'op': 'response',
            'result': '\'unknown "command_id"\'',
            'is_exception': True
        }
        yield self.send_msg_check_response(self.protocol, msg, expected)

    @defer.inlineCallbacks
    def test_missing_authorization_header(self):
        request = mock.Mock()
        request.headers = {"authorization": ''}
        request.peer = ''

        with self.assertRaises(Exception):
            yield self.protocol.onConnect(request)

    @defer.inlineCallbacks
    def test_auth_password_does_not_match(self):
        pfactory = mock.Mock()
        pfactory.connection = mock.Mock()

        self.setup_mock_users({'username': ('password', pfactory)})

        request = mock.Mock()
        request.headers = {
            "authorization": encode_http_authorization_header(b'username', b'wrong_password')
        }
        request.peer = ''

        with self.assertRaises(ConnectionDeny):
            yield self.protocol.onConnect(request)

    @defer.inlineCallbacks
    def test_auth_username_unknown(self):
        pfactory = mock.Mock()
        pfactory.connection = mock.Mock()

        self.setup_mock_users({'username': ('pass', pfactory)})

        request = mock.Mock()

        request.headers = {
            "authorization": encode_http_authorization_header(b'wrong_username', b'pass')
        }
        request.peer = ''

        with self.assertRaises(ConnectionDeny):
            yield self.protocol.onConnect(request)

    @defer.inlineCallbacks
    def test_update_success(self):
        yield self.connect_authenticated_worker()
        command_id = 1

        command = mock.Mock()
        self.protocol.command_id_to_command_map = {command_id: command}

        msg = {'op': 'update', 'args': 'args', 'command_id': command_id}
        expected = {'op': 'response', 'result': None}
        yield self.send_msg_check_response(self.protocol, msg, expected)
        command.remote_update_msgpack.assert_called_once_with(msg['args'])

    @defer.inlineCallbacks
    def test_complete_success(self):
        yield self.connect_authenticated_worker()
        command_id = 1

        command = mock.Mock()
        self.protocol.command_id_to_command_map = {command_id: command}
        self.protocol.command_id_to_reader_map = {}
        self.protocol.command_id_to_writer_map = {}

        msg = {'op': 'complete', 'args': 'args', 'command_id': command_id}
        expected = {'op': 'response', 'result': None}
        yield self.send_msg_check_response(self.protocol, msg, expected)
        command.remote_complete.assert_called_once()

    @defer.inlineCallbacks
    def test_complete_check_dict_removal(self):
        yield self.connect_authenticated_worker()
        command_id = 1

        command = mock.Mock()
        self.protocol.command_id_to_command_map = {command_id: command, 2: 'test_command'}
        self.protocol.command_id_to_reader_map = {command_id: 'test_reader', 2: 'test_reader2'}
        self.protocol.command_id_to_writer_map = {command_id: 'test_writer', 2: 'test_writer2'}

        msg = {'op': 'complete', 'args': 'args', 'command_id': command_id}
        expected = {'op': 'response', 'result': None}
        yield self.send_msg_check_response(self.protocol, msg, expected)
        command.remote_complete.assert_called_once()
        self.assertEqual(self.protocol.command_id_to_command_map, {2: 'test_command'})
        self.assertEqual(self.protocol.command_id_to_reader_map, {2: 'test_reader2'})
        self.assertEqual(self.protocol.command_id_to_writer_map, {2: 'test_writer2'})

    @defer.inlineCallbacks
    def test_update_upload_file_write_success(self):
        yield self.connect_authenticated_worker()
        command_id = 1

        command = mock.Mock()
        self.protocol.command_id_to_writer_map = {command_id: command}

        msg = {'op': 'update_upload_file_write', 'args': 'args', 'command_id': command_id}
        expected = {'op': 'response', 'result': None}
        yield self.send_msg_check_response(self.protocol, msg, expected)
        command.remote_write.assert_called_once()

    @defer.inlineCallbacks
    def test_update_upload_file_utime_missing_access_time(self):
        yield self.connect_authenticated_worker()
        msg = {
            'op': 'update_upload_file_utime',
            'modified_time': 2,
            'command_id': 2
        }
        expected = {
            'op': 'response',
            'result': '\'message did not contain obligatory "access_time" key\'',
            'is_exception': True
        }
        yield self.send_msg_check_response(self.protocol, msg, expected)

    @defer.inlineCallbacks
    def test_update_upload_file_utime_missing_modified_time(self):
        yield self.connect_authenticated_worker()
        msg = {
            'op': 'update_upload_file_utime',
            'access_time': 1,
            'command_id': 2
        }
        expected = {
            'op': 'response',
            'result': '\'message did not contain obligatory "modified_time" key\'',
            'is_exception': True
        }
        yield self.send_msg_check_response(self.protocol, msg, expected)

    @defer.inlineCallbacks
    def test_update_upload_file_utime_success(self):
        yield self.connect_authenticated_worker()
        command_id = 1

        command = mock.Mock()
        self.protocol.command_id_to_writer_map = {command_id: command}

        msg = {
            'op': 'update_upload_file_utime',
            'access_time': 1,
            'modified_time': 2,
            'command_id': command_id
        }
        expected = {'op': 'response', 'result': None}
        yield self.send_msg_check_response(self.protocol, msg, expected)
        command.remote_utime.assert_called_once_with('access_time', 'modified_time')

    @defer.inlineCallbacks
    def test_update_upload_file_close_success(self):
        yield self.connect_authenticated_worker()
        command_id = 1

        command = mock.Mock()
        self.protocol.command_id_to_writer_map = {command_id: command}

        msg = {'op': 'update_upload_file_close', 'command_id': command_id}
        expected = {'op': 'response', 'result': None}
        yield self.send_msg_check_response(self.protocol, msg, expected)
        command.remote_close.assert_called_once()

    @defer.inlineCallbacks
    def test_update_read_file_missing_length(self):
        yield self.connect_authenticated_worker()
        msg = {'op': 'update_read_file', 'command_id': 1}
        expected = {
            'op': 'response',
            'result': '\'message did not contain obligatory "length" key\'',
            'is_exception': True
        }
        yield self.send_msg_check_response(self.protocol, msg, expected)

    @defer.inlineCallbacks
    def test_update_read_file_success(self):
        yield self.connect_authenticated_worker()
        command_id = 1

        command = mock.Mock()
        self.protocol.command_id_to_reader_map = {command_id: command}

        msg = {'op': 'update_read_file', 'length': 1, 'command_id': command_id}
        expected = {'op': 'response', 'result': None}
        yield self.send_msg_check_response(self.protocol, msg, expected)
        command.remote_read.assert_called_once_with(msg['length'])

    @defer.inlineCallbacks
    def test_update_read_file_close_success(self):
        yield self.connect_authenticated_worker()
        command_id = 1

        command = mock.Mock()
        self.protocol.command_id_to_reader_map = {command_id: command}

        msg = {'op': 'update_read_file_close', 'command_id': command_id}
        expected = {'op': 'response', 'result': None}
        yield self.send_msg_check_response(self.protocol, msg, expected)
        command.remote_close.assert_called_once()

    @defer.inlineCallbacks
    def test_update_upload_directory_unpack_success(self):
        yield self.connect_authenticated_worker()
        command_id = 1

        command = mock.Mock()
        self.protocol.command_id_to_writer_map = {command_id: command}

        msg = {'op': 'update_upload_directory_unpack', 'command_id': command_id}
        expected = {'op': 'response', 'result': None}
        yield self.send_msg_check_response(self.protocol, msg, expected)
        command.remote_unpack.assert_called_once()

    @defer.inlineCallbacks
    def test_update_upload_directory_write_success(self):
        yield self.connect_authenticated_worker()
        command_id = 1

        command = mock.Mock()
        self.protocol.command_id_to_writer_map = {command_id: command}

        msg = {
            'op': 'update_upload_directory_write',
            'command_id': command_id,
            'args': 'args'
        }
        expected = {'op': 'response', 'result': None}
        yield self.send_msg_check_response(self.protocol, msg, expected)
        command.remote_write.assert_called_once_with(msg['args'])

    def test_onMessage_not_isBinary(self):
        # if isBinary is False, sendMessage should not be called
        msg = {}
        self.protocol.onMessage(msgpack.packb(msg), False)
        self.seq_number += 1
        self.protocol.sendMessage.assert_not_called()

    @defer.inlineCallbacks
    def test_onMessage_worker_not_authenticated(self):
        msg = {'op': 'update', 'command_id': 1, 'args': 'test'}
        expected = {
            'op': 'response',
            'result': 'Worker not authenticated.',
            'is_exception': True,
        }
        yield self.send_msg_check_response(self.protocol, msg, expected)

    @defer.inlineCallbacks
    def test_onMessage_command_does_not_exist(self):
        yield self.connect_authenticated_worker()
        msg = {'op': 'test'}
        expected = {
            'op': 'response',
            'result': 'Command test does not exist.',
            'is_exception': True,
        }
        yield self.send_msg_check_response(self.protocol, msg, expected)

    @defer.inlineCallbacks
    def test_get_message_result_success(self):
        yield self.connect_authenticated_worker()
        msg = {'op': 'getWorkerInfo'}
        d = self.protocol.get_message_result(msg)
        seq_num = msg['seq_number']
        self.assertEqual(d.called, False)

        self.protocol.sendMessage.assert_called()

        # master got an answer from worker through onMessage
        msg = {'seq_number': seq_num, 'op': 'response', 'result': 'test_result'}
        self.protocol.onMessage(msgpack.packb(msg), isBinary=True)
        self.assertEqual(d.called, True)
        res = yield d
        self.assertEqual(res, 'test_result')

    @defer.inlineCallbacks
    def test_get_message_result_failed(self):
        yield self.connect_authenticated_worker()
        msg = {'op': 'getWorkerInfo'}
        d = self.protocol.get_message_result(msg)
        seq_num = msg['seq_number']
        self.assertEqual(d.called, False)

        # Master got an answer from worker through onMessage.
        # This time the message indicates failure
        msg_response = {
            'seq_number': seq_num,
            'op': 'response',
            'is_exception': True,
            'result': 'error_result'
        }
        self.protocol.onMessage(msgpack.packb(msg_response), isBinary=True)
        self.assertEqual(d.called, True)
        with self.assertRaises(RemoteWorkerError):
            yield d

    @defer.inlineCallbacks
    def test_get_message_result_no_worker_connection(self):
        # master can not send any messages if connection is not established
        with self.assertRaises(ConnectioLostError):
            yield self.protocol.get_message_result({'op': 'getWorkerInfo'})

    @defer.inlineCallbacks
    def test_onClose_connection_lost_error(self):
        yield self.connect_authenticated_worker()
        # master sends messages for worker and waits for their response
        msg = {'op': 'getWorkerInfo'}
        d1 = self.protocol.get_message_result(msg)
        self.assertEqual(d1.called, False)

        msg = {'op': 'print', 'message': 'test'}
        d2 = self.protocol.get_message_result(msg)
        self.assertEqual(d2.called, False)

        # Worker disconnected, master will never get the response message.
        # Stop waiting and raise Exception
        self.protocol.onClose(True, None, 'worker is gone')
        self.assertEqual(d1.called, True)
        with self.assertRaises(ConnectioLostError):
            yield d1

        self.assertEqual(d2.called, True)
        with self.assertRaises(ConnectioLostError):
            yield d2

        self.protocol.connection.detached.assert_called()
        # contents of dict_def are deleted to stop waiting for the responses of all commands
        self.assertEqual(len(self.protocol.seq_num_to_waiters_map), 0)
