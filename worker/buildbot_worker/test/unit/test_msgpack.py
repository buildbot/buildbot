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
import os
import sys
import time

from parameterized import parameterized

import mock

from twisted.application import service
from twisted.internet import defer
from twisted.internet import reactor
from twisted.trial import unittest

from buildbot_worker import base
from buildbot_worker import pb
from buildbot_worker import util
from buildbot_worker.test.fake.runprocess import Expect
from buildbot_worker.test.util import command

if sys.version_info >= (3, 6):
    import msgpack
    # pylint: disable=ungrouped-imports
    from buildbot_worker.msgpack import decode_http_authorization_header
    from buildbot_worker.msgpack import encode_http_authorization_header
    from buildbot_worker.msgpack import BuildbotWebSocketClientProtocol
    from buildbot_worker.pb import BotMsgpack  # pylint: disable=ungrouped-imports


class TestHttpAuthorization(unittest.TestCase):
    maxDiff = None
    if sys.version_info < (3, 6):
        skip = "Not python 3.6 or newer"

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


class FakeStep(object):

    "A fake master-side BuildStep that records its activities."

    def __init__(self):
        self.finished_d = defer.Deferred()
        self.actions = []

    def wait_for_finish(self):
        return self.finished_d

    def remote_update(self, updates):
        for update in updates:
            if 'elapsed' in update[0]:
                update[0]['elapsed'] = 1
        self.actions.append(["update", updates])

    def remote_complete(self, f):
        self.actions.append(["complete", f])
        self.finished_d.callback(None)


class FakeBot(base.BotBase):
    WorkerForBuilder = pb.WorkerForBuilderPbLike


class TestBuildbotWebSocketClientProtocol(command.CommandTestMixin, unittest.TestCase):
    maxDiff = None
    if sys.version_info < (3, 6):
        skip = "Not python 3"

    def setUp(self):
        self.protocol = BuildbotWebSocketClientProtocol()
        self.protocol.sendMessage = mock.Mock()
        self.protocol.factory = mock.Mock()
        self.protocol.factory.password = b'test_password'
        self.protocol.factory.name = b'test_username'

        self.protocol.factory.buildbot_bot.builders = {'test_builder': mock.Mock()}
        self.protocol.dict_def = {}
        self.protocol.sendClose = mock.Mock()

        def mock_util_now(_reactor=None):
            return 0

        # patch util.now function to never let tests access the time module of the code
        self.patch(util, 'now', mock_util_now)

        self.list_send_message_args = []

        def send_message_test(payload, isBinary):
            msg = msgpack.unpackb(payload, raw=False)
            self.list_send_message_args.append(msg)

        self.protocol.sendMessage = send_message_test

    def assert_sent_messages(self, msgs_expected):
        # checks, what messages has been called in sendMessage
        self.assertEqual(msgs_expected, self.list_send_message_args)
        self.list_send_message_args[:] = []

    def setup_with_worker_for_builder(self):
        self.protocol.onOpen()
        # we are not interested in list_send_message_args before onMessage was called by test
        self.list_send_message_args[:] = []
        self.protocol.factory.buildbot_bot = BotMsgpack('test/dir')
        service.MultiService.startService(self.protocol.factory.buildbot_bot)

        self.protocol.factory.buildbot_bot.builder_protocol_command = {'test_builder': None}
        self.protocol.factory.buildbot_bot.builder_basedirs = {'test_builder': 'basedir'}

    @defer.inlineCallbacks
    def test_call_get_worker_info_success(self):
        self.protocol.factory.buildbot_bot.remote_getWorkerInfo = mock.Mock()
        self.protocol.factory.buildbot_bot.remote_getWorkerInfo.return_value = {
            'test': 'data_about_worker'}

        msg = {'op': 'get_worker_info', 'seq_number': 0}
        self.protocol.onMessage(msgpack.packb(msg), True)
        yield self.protocol._deferwaiter.wait()

        self.protocol.factory.buildbot_bot.remote_getWorkerInfo.assert_called()

        msgs_expected = {'op': 'response', 'seq_number': 0, 'result': {'test': 'data_about_worker'}}
        self.assertEqual(self.list_send_message_args, [msgs_expected])

    @defer.inlineCallbacks
    def send_message(self, message):
        self.protocol.onMessage(msgpack.packb(message), True)
        yield self.protocol._deferwaiter.wait()

    @parameterized.expand([
        ('print_op', {'seq_number': 1, 'message': 'test'}),
        ('print_seq_number', {'op': 'print', 'message': 'test'}),
        ('keepalive_op', {'seq_number': 1}),
        ('keepalive_seq_number', {'op': 'keepalive'}),
        ('get_worker_info_op', {'seq_number': 1}),
        ('get_worker_info_seq_number', {'op': 'get_worker_info'}),
        ('start_command_op', {'seq_number': 1}),
        ('start_command_seq_number', {'op': 'start_command'}),
        ('shutdown_op', {'seq_number': 1}),
        ('shutdown_seq_number', {'op': 'shutdown'}),
        ('interrupt_command_op', {'seq_number': 1}),
        ('interrupt_command_seq_number', {'op': 'interrupt_command'}),
        ('response_op', {'seq_number': 1}),
        ('response_seq_number', {'op': 'response'}),
    ])
    @defer.inlineCallbacks
    def test_msg(self, name, msg):
        # if msg does not have 'sep_number' or 'op', response sendMessage should not be called
        with mock.patch('twisted.python.log.msg') as mock_log:
            yield self.send_message(msg)
            mock_log.assert_any_call('Invalid message from master: {}'.format(msg))

        self.assert_sent_messages([])

    @parameterized.expand([
        (
            'start_command', {
                'op': 'start_command',
                'seq_number': 1,
                'command_name': 'test_command',
                'args': 'args'
            },
            'command_id'
        ), (
            'start_command', {
                'op': 'start_command',
                'seq_number': 1,
                'command_id': '123',
                'command_name': 'test_command',
            },
            'args'
        ), (
            'start_command', {
                'op': 'start_command',
                'seq_number': 1,
                'command_id': '123',
                'args': 'args'
            },
            'command_name'
        ), (
            'interrupt_command', {
                'op': 'interrupt_command',
                'seq_number': 1,
                'why': 'test_why'
            },
            'command_id'
        ), (
            'call_print', {
                'op': 'print',
                'seq_number': 1
            },
            'message'
        ), (
            'call_interrupt_command', {
                'op': 'interrupt_command',
                'seq_number': 1,
                'command_id': '123'
            },
            'why'
        ), (
            'call_interrupt_command', {
                'op': 'interrupt_command',
                'seq_number': 1,
                'why': 'test_reason'
            },
            'command_id'
        )])
    @defer.inlineCallbacks
    def test_missing_parameter(self, command, msg, missing_parameter):
        self.protocol.onOpen()
        # we are not interested in list_send_message_args before onMessage was called by test
        self.list_send_message_args[:] = []
        yield self.send_message(msg)
        self.assert_sent_messages([{
            'op': 'response',
            'seq_number': 1,
            'result': '\'message did not contain obligatory "{0}" key\''.format(missing_parameter),
            'is_exception': True
        }])

    @defer.inlineCallbacks
    def test_on_message_unrecognized_command(self):
        self.protocol.onOpen()
        # we are not interested in list_send_message_args before onMessage was called by test
        self.list_send_message_args[:] = []

        yield self.send_message({'op': 'test', 'seq_number': 0})

        self.assert_sent_messages([{
            'is_exception': True,
            'op': 'response',
            'result': 'Command test does not exist.',
            'seq_number': 0
        }])

    def test_authorization_header(self):
        result = self.protocol.onConnecting('test')

        self.assertEqual(result.headers, {
            "Authorization": encode_http_authorization_header(b'test_username', b'test_password')
        })

    @defer.inlineCallbacks
    def test_call_print_success(self):
        self.protocol.factory.buildbot_bot = BotMsgpack('test/dir')
        with mock.patch('twisted.python.log.msg') as mock_log:
            yield self.send_message({'op': 'print', 'seq_number': 0, 'message': 'test_message'})
            mock_log.assert_any_call("message from master:", 'test_message')

        self.assert_sent_messages([{'op': 'response', 'seq_number': 0, 'result': None}])

    @defer.inlineCallbacks
    def test_call_keepalive(self):
        with mock.patch('twisted.python.log.msg') as mock_log:
            yield self.send_message({'op': 'keepalive', 'seq_number': 0})
            mock_log.assert_any_call("Connection keepalive confirmed.")

        self.assert_sent_messages([{'op': 'response', 'seq_number': 0, 'result': None}])

    @defer.inlineCallbacks
    def test_call_start_command_success(self):
        self.setup_with_worker_for_builder()

        # check if directory was created
        with mock.patch('os.makedirs') as mkdir:
            yield self.send_message({
                'op': 'start_command',
                'seq_number': 0,
                'command_id': '123',
                'command_name': 'mkdir',
                'args': {'paths': ['basedir/test_dir'], 'test1': 'value1', 'test2': 'value2'}
            })
            mkdir.assert_called()

    @defer.inlineCallbacks
    def test_call_start_command_failed(self):
        self.patch(time, 'time', lambda: 123.0)
        self.setup_with_worker_for_builder()

        path = os.path.join('basedir', 'test_dir')
        # check if directory was created
        with mock.patch('os.makedirs') as mkdir:
            mkdir.side_effect = OSError(1, 'test_error')
            yield self.send_message({
                'op': 'start_command',
                'seq_number': 1,
                'command_id': '123',
                'command_name': 'mkdir',
                'args': {'paths': [path], 'test1': 'value1', 'test2': 'value2'}
            })
            mkdir.assert_called()

        self.assert_sent_messages([
            {
                'op': 'update',
                'args': [
                    ['rc', 1],
                    ['elapsed', 0],
                    ['header', ['mkdir: test_error: {}\n'.format(path), [35], [123.0]]]
                ],
                'command_id': '123',
                'seq_number': 0
            }, {
                'op': 'complete',
                'args': None,
                'command_id': '123',
                'seq_number': 1
            },
            # response result is always None, even if the command failed
            {'op': 'response', 'result': None, 'seq_number': 1}
        ])

        def create_msg(seq_number):
            return {
                'op': 'response',
                'seq_number': seq_number,
                'result': None
            }

        yield self.send_message(create_msg(0))
        yield self.send_message(create_msg(1))

        # worker should not send any new messages in response to masters 'response'
        self.assertEqual(self.list_send_message_args, [])

    @defer.inlineCallbacks
    def test_call_start_command_shell_success(self):
        self.patch(time, 'time', lambda: 123.0)
        self.setup_with_worker_for_builder()

        # patch runprocess to handle the 'echo', below
        workdir = os.path.join('basedir', 'test_basedir')
        self.patch_runprocess(
            Expect(['echo'], workdir)
            .update('header', 'headers')  # note that this is partial line
            .update('stdout', 'hello\n')
            .update('rc', 0)
            .exit(0)
            )

        yield self.send_message({
            'op': 'start_command',
            'seq_number': 1,
            'command_id': '123',
            'command_name': 'shell',
            'args': {'command': ['echo'], 'workdir': workdir}
        })

        self.assert_sent_messages([
            {
                'op': 'update',
                'args': [
                    ['stdout', ['hello\n', [5], [123.0]]],
                    ['rc', 0],
                    ['elapsed', 0],
                    ['header', ['headers\n', [7], [123.0]]]
                ],
                'command_id': '123',
                'seq_number': 0
            }, {
                'op': 'complete',
                'args': None,
                'command_id': '123',
                'seq_number': 1
            }, {
                'op': 'response', 'seq_number': 1, 'result': None
            }
        ])

    @defer.inlineCallbacks
    def test_call_start_command_shell_success_logs(self):
        self.patch(time, 'time', lambda: 123.0)
        self.setup_with_worker_for_builder()

        workdir = os.path.join('basedir', 'test_basedir')
        self.patch_runprocess(
            Expect(['echo'], workdir)
            .update('header', 'headers\n')
            .update('log', ('test_log', ('hello')))
            .update('log', ('test_log', ('hello1\n')))
            .update('log', ('test_log2', ('hello2\n')))
            .update('log', ('test_log3', ('hello3')))
            .update('rc', 0)
            .exit(0)
            )

        yield self.send_message({
            'op': 'start_command',
            'seq_number': 1,
            'command_id': '123',
            'command_name': 'shell',
            'args': {'command': ['echo'], 'workdir': workdir}
        })

        self.assert_sent_messages([
            {
                'op': 'update',
                'args': [
                    ['header', ['headers\n', [7], [123.0]]],
                    ['log', ['test_log', ['hellohello1\n', [11], [123.0]]]],
                    ['log', ['test_log2', ['hello2\n', [6], [123.0]]]],
                    ['rc', 0],
                    ['elapsed', 0],
                    ['log', ['test_log3', ['hello3\n', [6], [123.0]]]],
                ],
                'command_id': '123',
                'seq_number': 0
            }, {
                'op': 'complete',
                'args': None,
                'command_id': '123',
                'seq_number': 1
            }, {
                'op': 'response', 'seq_number': 1, 'result': None
            }
        ])

    @defer.inlineCallbacks
    def test_start_command_shell_success_updates_single(self):
        self.patch(time, 'time', lambda: 123.0)
        self.setup_with_worker_for_builder()

        # patch runprocess to handle the 'echo', below
        workdir = os.path.join('basedir', 'test_basedir')
        self.patch_runprocess(
            Expect(['echo'], workdir)
            .updates([('header', 'headers'), ('stdout', 'hello\n'), ('rc', 0)])
            .exit(0)
            )

        yield self.send_message({
            'op': 'start_command',
            'seq_number': 1,
            'command_id': '123',
            'command_name': 'shell',
            'args': {'command': ['echo'], 'workdir': workdir}
        })

        self.assert_sent_messages([
            {
                'op': 'update',
                'args': [
                    ['stdout', ['hello\n', [5], [123.0]]],
                    ['rc', 0],
                    ['elapsed', 0],
                    ['header', ['headers\n', [7], [123.0]]]
                ],
                'command_id': '123',
                'seq_number': 0
            }, {
                'op': 'complete',
                'args': None,
                'command_id': '123',
                'seq_number': 1
            }, {
                'op': 'response', 'seq_number': 1, 'result': None
            }
        ])

    @defer.inlineCallbacks
    def test_call_shutdown_success(self):
        # shutdown stops reactor, we can not test it so we just mock
        self.protocol.factory.buildbot_bot.remote_shutdown = mock.Mock()

        yield self.send_message({'op': 'shutdown', 'seq_number': 0})

        self.protocol.factory.buildbot_bot.remote_shutdown.assert_called()

    @defer.inlineCallbacks
    def test_call_interrupt_command_no_command_to_interrupt(self):
        self.setup_with_worker_for_builder()
        self.protocol.factory.command.doInterrupt = mock.Mock()

        with mock.patch('twisted.python.log.msg') as mock_log:
            yield self.send_message({
                'op': 'interrupt_command',
                'seq_number': 1,
                'command_id': '123',
                'why': 'test_reason'
            })
            mock_log.assert_any_call(
                'asked to interrupt current command: {0}'.format('test_reason'))
            mock_log.assert_any_call(' .. but none was running')

        self.protocol.factory.command.doInterrupt.assert_not_called()

    @defer.inlineCallbacks
    def test_call_interrupt_command_success(self):
        self.patch(time, 'time', lambda: 123.0)
        self.setup_with_worker_for_builder()
        self.protocol.factory.command.doInterrupt = mock.Mock()

        # patch runprocess to pretend to sleep (it will really just hang forever,
        # except that we interrupt it)
        workdir = os.path.join('basedir', 'test_basedir')
        self.patch_runprocess(
            Expect(['sleep', '10'], workdir)
            .update('header', 'headers')
            .update('wait', True)
        )

        yield self.send_message({
            'op': 'start_command',
            'seq_number': 1,
            'command_id': '123',
            'command_name': 'shell',
            'args': {'command': ['sleep', '10'], 'workdir': workdir}
        })

        # wait a jiffy..
        d = defer.Deferred()
        reactor.callLater(0.01, d.callback, None)
        yield d

        self.assert_sent_messages([
            {
                'op': 'response',
                'seq_number': 1,
                'result': None
            }
        ])

        yield self.send_message({
            'op': 'interrupt_command',
            'seq_number': 1,
            'command_id': '123',
            'why': 'test_reason'
        })

        self.assert_sent_messages([
            {
                'op': 'update',
                'seq_number': 0,
                'command_id': '123',
                'args': [['header', ['headers\n', [7], [123.0]]]]
            }, {
                'op': 'update',
                'seq_number': 1,
                'command_id': '123',
                'args': [['rc', -1], ['header', ['killing\n', [7], [123.0]]]],
            }, {
                'op': 'complete', 'seq_number': 2, 'command_id': '123', 'args': None
            }, {
                'op': 'response', 'seq_number': 1, 'result': None
            }
    ])
