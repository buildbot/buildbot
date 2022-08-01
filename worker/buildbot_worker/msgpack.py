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

from __future__ import absolute_import
from __future__ import print_function

import base64

import msgpack

from autobahn.twisted.websocket import WebSocketClientFactory
from autobahn.twisted.websocket import WebSocketClientProtocol
from autobahn.websocket.types import ConnectingRequest
from twisted.internet import defer
from twisted.python import log

from buildbot_worker.base import ProtocolCommandBase
from buildbot_worker.util import deferwaiter


class RemoteWorkerError(Exception):
    pass


def decode_http_authorization_header(value):
    if value[:5] != 'Basic':
        raise ValueError("Value should always start with 'Basic'")

    credentials_str = base64.b64decode(value[6:]).decode()
    if ':' not in credentials_str:
        raise ValueError("String of credentials should always have a colon.")

    username, password = credentials_str.split(':', maxsplit=1)
    return (username, password)


def encode_http_authorization_header(name, password):
    if b":" in name:
        raise ValueError("Username is not allowed to contain a colon.")
    userpass = name + b':' + password
    return 'Basic ' + base64.b64encode(userpass).decode()


def remote_print(self, message):
    log.msg("WorkerForBuilder.remote_print({0}): message from master: {1}".format(
            self.name, message))


class ProtocolCommandMsgpack(ProtocolCommandBase):
    def __init__(self, unicode_encoding, worker_basedir, buffer_size, buffer_timeout,
                 max_line_length, newline_re, builder_is_running,
                 on_command_complete, protocol, command_id, command, args):
        ProtocolCommandBase.__init__(self, unicode_encoding, worker_basedir, buffer_size,
                                     buffer_timeout, max_line_length, newline_re,
                                     builder_is_running, on_command_complete, None, command,
                                     command_id, args)
        self.protocol = protocol
        self.command_id = command_id

    def protocol_args_setup(self, command, args):
        if "want_stdout" in args:
            if args["want_stdout"]:
                args["want_stdout"] = 1
            else:
                args["want_stdout"] = 0

        if "want_stderr" in args:
            if args["want_stderr"]:
                args["want_stderr"] = 1
            else:
                args["want_stderr"] = 0

        # to silence the ValueError in class Command() init
        if (command in ("upload_directory", "upload_file")) and 'writer' not in args:
            args['writer'] = None
        if command == "download_file" and 'reader' not in args:
            args['reader'] = None

    def protocol_send_update_message(self, message):
        d = self.protocol.get_message_result({'op': 'update', 'args': message,
                                              'command_id': self.command_id})
        d.addErrback(self._ack_failed, "ProtocolCommandBase.send_update")

    def protocol_notify_on_disconnect(self):
        pass

    @defer.inlineCallbacks
    def protocol_complete(self, failure):
        d_update = self.flush_command_output()
        if failure is not None:
            failure = str(failure)
        d_complete = self.protocol.get_message_result({'op': 'complete', 'args': failure,
                                                       'command_id': self.command_id})
        yield d_update
        yield d_complete

    # Returns a Deferred
    def protocol_update_upload_file_close(self, writer):
        return self.protocol.get_message_result({'op': 'update_upload_file_close',
                                                 'command_id': self.command_id})

    # Returns a Deferred
    def protocol_update_upload_file_utime(self, writer, access_time, modified_time):
        return self.protocol.get_message_result({'op': 'update_upload_file_utime',
                                                 'access_time': access_time,
                                                 'modified_time': modified_time,
                                                 'command_id': self.command_id})

    # Returns a Deferred
    def protocol_update_upload_file_write(self, writer, data):
        return self.protocol.get_message_result({'op': 'update_upload_file_write', 'args': data,
                                                 'command_id': self.command_id})

    # Returns a Deferred
    def protocol_update_upload_directory(self, writer):
        return self.protocol.get_message_result({'op': 'update_upload_directory_unpack',
                                                 'command_id': self.command_id})

    # Returns a Deferred
    def protocol_update_upload_directory_write(self, writer, data):
        return self.protocol.get_message_result({'op': 'update_upload_directory_write',
                                                 'args': data, 'command_id': self.command_id})

    # Returns a Deferred
    def protocol_update_read_file_close(self, reader):
        return self.protocol.get_message_result({'op': 'update_read_file_close',
                                                 'command_id': self.command_id})

    # Returns a Deferred
    def protocol_update_read_file(self, reader, length):
        return self.protocol.get_message_result({'op': 'update_read_file', 'length': length,
                                                 'command_id': self.command_id})


class ConnectionLostError(Exception):
    pass


class BuildbotWebSocketClientProtocol(WebSocketClientProtocol):
    debug = True

    def __init__(self):
        super(BuildbotWebSocketClientProtocol, self).__init__()
        self.seq_num_to_waiters_map = {}
        self._deferwaiter = deferwaiter.DeferWaiter()

    def onConnect(self, response):
        if self.debug:
            log.msg("Server connected: {0}".format(response.peer))

    def onConnecting(self, transport_details):
        if self.debug:
            log.msg("Connecting; transport details: {}".format(transport_details))

        auth_header = encode_http_authorization_header(self.factory.name, self.factory.password)

        return ConnectingRequest(
            host=self.factory.host,
            port=self.factory.port,
            resource=self.factory.resource,
            headers={"Authorization": auth_header},
            useragent=self.factory.useragent,
            origin=self.factory.origin,
            protocols=self.factory.protocols
        )

    def maybe_log_worker_to_master_msg(self, message):
        if self.debug:
            log.msg("WORKER -> MASTER message: ", message)

    def maybe_log_master_to_worker_msg(self, message):
        if self.debug:
            log.msg("MASTER -> WORKER message: ", message)

    def contains_msg_key(self, msg, keys):
        for k in keys:
            if k not in msg:
                raise KeyError('message did not contain obligatory "{}" key'.format(k))

    def onOpen(self):
        if self.debug:
            log.msg("WebSocket connection open.")
        self.seq_number = 0

    def call_print(self, msg):
        is_exception = False
        try:
            self.contains_msg_key(msg, ('message',))
            self.factory.buildbot_bot.remote_print(msg['message'])
            result = None
        except Exception as e:
            is_exception = True
            result = str(e)

        self.send_response_msg(msg, result, is_exception)

    def call_keepalive(self, msg):
        result = None
        is_exception = False
        try:
            if self.debug:
                log.msg("Connection keepalive confirmed.")
        except Exception:
            pass

        self.send_response_msg(msg, result, is_exception)

    @defer.inlineCallbacks
    def call_get_worker_info(self, msg):
        is_exception = False
        try:
            result = yield self.factory.buildbot_bot.remote_getWorkerInfo()
        except Exception as e:
            is_exception = True
            result = str(e)
        self.send_response_msg(msg, result, is_exception)

    def call_set_worker_settings(self, msg):
        is_exception = False
        try:
            self.contains_msg_key(msg, ('args',))
            for setting in ["buffer_size", "buffer_timeout", "newline_re", "max_line_length"]:
                if setting not in msg["args"]:
                    raise KeyError('message did not contain obligatory settings for worker')

            self.factory.buildbot_bot.buffer_size = msg["args"]["buffer_size"]
            self.factory.buildbot_bot.buffer_timeout = msg["args"]["buffer_timeout"]
            self.factory.buildbot_bot.newline_re = msg["args"]["newline_re"]
            self.factory.buildbot_bot.max_line_length = msg["args"]["max_line_length"]
            result = None
        except Exception as e:
            is_exception = True
            result = str(e)

        self.send_response_msg(msg, result, is_exception)

    @defer.inlineCallbacks
    def call_start_command(self, msg):
        is_exception = False
        try:
            self.contains_msg_key(msg, ('command_id', 'command_name', 'args'))
            # send an instance, on which get_message_result will be called
            yield self.factory.buildbot_bot.start_command(self, msg['command_id'],
                                                          msg['command_name'], msg['args'])
            result = None
        except Exception as e:
            is_exception = True
            result = str(e)

        self.send_response_msg(msg, result, is_exception)

    @defer.inlineCallbacks
    def call_shutdown(self, msg):
        is_exception = False
        try:
            yield self.factory.buildbot_bot.remote_shutdown()
            result = None
        except Exception as e:
            is_exception = True
            result = str(e)

        self.send_response_msg(msg, result, is_exception)

    @defer.inlineCallbacks
    def call_interrupt_command(self, msg):
        is_exception = False
        try:
            self.contains_msg_key(msg, ('command_id', 'why'))
            # send an instance, on which get_message_result will be called
            yield self.factory.buildbot_bot.interrupt_command(msg['command_id'], msg['why'])
            result = None
        except Exception as e:
            is_exception = True
            result = str(e)
        self.send_response_msg(msg, result, is_exception)

    def send_response_msg(self, msg, result, is_exception):
        dict_output = {
            'op': 'response',
            'seq_number': msg['seq_number'],
            'result': result
        }

        if is_exception:
            dict_output['is_exception'] = True
        self.maybe_log_worker_to_master_msg(dict_output)
        payload = msgpack.packb(dict_output)
        self.sendMessage(payload, isBinary=True)

    def onMessage(self, payload, isBinary):
        if not isBinary:
            log.msg('Message type form master unsupported')
            return

        msg = msgpack.unpackb(payload, raw=False)
        self.maybe_log_master_to_worker_msg(msg)

        if 'seq_number' not in msg or 'op' not in msg:
            log.msg('Invalid message from master: {}'.format(msg))
            return
        if msg['op'] == "print":
            self._deferwaiter.add(self.call_print(msg))
        elif msg['op'] == "keepalive":
            self._deferwaiter.add(self.call_keepalive(msg))
        elif msg['op'] == "set_worker_settings":
            self._deferwaiter.add(self.call_set_worker_settings(msg))
        elif msg['op'] == "get_worker_info":
            self._deferwaiter.add(self.call_get_worker_info(msg))
        elif msg['op'] == "start_command":
            self._deferwaiter.add(self.call_start_command(msg))
        elif msg['op'] == "shutdown":
            self._deferwaiter.add(self.call_shutdown(msg))
        elif msg['op'] == "interrupt_command":
            self._deferwaiter.add(self.call_interrupt_command(msg))
        elif msg['op'] == "response":
            seq_number = msg['seq_number']
            if "is_exception" in msg:
                self.seq_num_to_waiters_map[seq_number].errback(RemoteWorkerError(msg['result']))
            else:
                self.seq_num_to_waiters_map[seq_number].callback(msg['result'])
            # stop waiting for a response of this command
            del self.seq_num_to_waiters_map[seq_number]
        else:
            self.send_response_msg(msg, "Command {} does not exist.".format(msg['op']),
                                   is_exception=True)

    @defer.inlineCallbacks
    def get_message_result(self, msg):
        msg['seq_number'] = self.seq_number
        self.maybe_log_worker_to_master_msg(msg)
        msg = msgpack.packb(msg)
        d = defer.Deferred()
        self.seq_num_to_waiters_map[self.seq_number] = d
        self.seq_number = self.seq_number + 1
        self.sendMessage(msg, isBinary=True)
        res1 = yield d
        defer.returnValue(res1)

    def onClose(self, wasClean, code, reason):
        if self.debug:
            log.msg("WebSocket connection closed: {0}".format(reason))
        # stop waiting for the responses of all commands
        for seq_number in self.seq_num_to_waiters_map:
            self.seq_num_to_waiters_map[seq_number].errback(ConnectionLostError("Connection lost"))
        self.seq_num_to_waiters_map.clear()


class BuildbotWebSocketClientFactory(WebSocketClientFactory):
    def waitForCompleteShutdown(self):
        pass
