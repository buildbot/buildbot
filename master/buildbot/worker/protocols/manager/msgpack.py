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

from autobahn.twisted.websocket import WebSocketServerFactory
from autobahn.twisted.websocket import WebSocketServerProtocol
from autobahn.websocket.types import ConnectionDeny
from twisted.internet import defer
from twisted.python import log

from buildbot.util import deferwaiter
from buildbot.util.eventual import eventually
from buildbot.worker.protocols.manager.base import BaseDispatcher
from buildbot.worker.protocols.manager.base import BaseManager


class ConnectioLostError(Exception):
    pass


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


class BuildbotWebSocketServerProtocol(WebSocketServerProtocol):
    debug = True

    def __init__(self):
        super().__init__()
        self.seq_num_to_waiters_map = {}
        self.connection = None
        self.worker_name = None
        self._deferwaiter = deferwaiter.DeferWaiter()

    def get_dispatcher(self):
        # This is an instance of class msgpack.Dispatcher set in Dispatcher.__init__().
        # self.factory is set on the protocol instance when creating it in Twisted internals
        return self.factory.buildbot_dispatcher

    @defer.inlineCallbacks
    def onOpen(self):
        if self.debug:
            log.msg("WebSocket connection open.")
        self.seq_number = 0
        self.command_id_to_command_map = {}
        self.command_id_to_reader_map = {}
        self.command_id_to_writer_map = {}
        yield self.initialize()

    def maybe_log_worker_to_master_msg(self, message):
        if self.debug:
            log.msg("WORKER -> MASTER message: ", message)

    def maybe_log_master_to_worker_msg(self, message):
        if self.debug:
            log.msg("MASTER -> WORKER message: ", message)

    def contains_msg_key(self, msg, keys):
        for k in keys:
            if k not in msg:
                raise KeyError(f'message did not contain obligatory "{k}" key')

    @defer.inlineCallbacks
    def initialize(self):
        try:
            dispatcher = self.get_dispatcher()
            yield dispatcher.master.initLock.acquire()

            if self.worker_name in dispatcher.users:
                _, afactory = dispatcher.users[self.worker_name]
                self.connection = yield afactory(self, self.worker_name)
                yield self.connection.attached(self)
            else:
                self.sendClose()
        except Exception as e:
            log.msg(f"Connection opening failed: {e}")
            self.sendClose()
        finally:
            eventually(dispatcher.master.initLock.release)

    @defer.inlineCallbacks
    def call_update(self, msg):
        result = None
        is_exception = False
        try:
            self.contains_msg_key(msg, ('command_id', 'args'))

            if msg['command_id'] not in self.command_id_to_command_map:
                raise KeyError('unknown "command_id"')

            command = self.command_id_to_command_map[msg['command_id']]
            yield command.remote_update_msgpack(msg['args'])
        except Exception as e:
            is_exception = True
            result = str(e)

        self.send_response_msg(msg, result, is_exception)

    @defer.inlineCallbacks
    def call_complete(self, msg):
        result = None
        is_exception = False
        try:
            self.contains_msg_key(msg, ('command_id', 'args'))

            if msg['command_id'] not in self.command_id_to_command_map:
                raise KeyError('unknown "command_id"')
            command = self.command_id_to_command_map[msg['command_id']]
            yield command.remote_complete(msg['args'])

            if msg['command_id'] in self.command_id_to_command_map:
                del self.command_id_to_command_map[msg['command_id']]
            if msg['command_id'] in self.command_id_to_reader_map:
                del self.command_id_to_reader_map[msg['command_id']]
            if msg['command_id'] in self.command_id_to_writer_map:
                del self.command_id_to_writer_map[msg['command_id']]
        except Exception as e:
            is_exception = True
            result = str(e)
        self.send_response_msg(msg, result, is_exception)

    @defer.inlineCallbacks
    def call_update_upload_file_write(self, msg):
        result = None
        is_exception = False
        try:
            self.contains_msg_key(msg, ('command_id', 'args'))

            if msg['command_id'] not in self.command_id_to_writer_map:
                raise KeyError('unknown "command_id"')

            file_writer = self.command_id_to_writer_map[msg['command_id']]
            yield file_writer.remote_write(msg['args'])
        except Exception as e:
            is_exception = True
            result = str(e)
        self.send_response_msg(msg, result, is_exception)

    @defer.inlineCallbacks
    def call_update_upload_file_utime(self, msg):
        result = None
        is_exception = False
        try:
            self.contains_msg_key(msg, ('command_id', 'access_time', 'modified_time'))

            if msg['command_id'] not in self.command_id_to_writer_map:
                raise KeyError('unknown "command_id"')

            file_writer = self.command_id_to_writer_map[msg['command_id']]
            yield file_writer.remote_utime('access_time', 'modified_time')
        except Exception as e:
            is_exception = True
            result = str(e)
        self.send_response_msg(msg, result, is_exception)

    @defer.inlineCallbacks
    def call_update_upload_file_close(self, msg):
        result = None
        is_exception = False
        try:
            self.contains_msg_key(msg, ('command_id',))

            if msg['command_id'] not in self.command_id_to_writer_map:
                raise KeyError('unknown "command_id"')

            file_writer = self.command_id_to_writer_map[msg['command_id']]
            yield file_writer.remote_close()
        except Exception as e:
            is_exception = True
            result = str(e)
        self.send_response_msg(msg, result, is_exception)

    @defer.inlineCallbacks
    def call_update_read_file(self, msg):
        result = None
        is_exception = False
        try:
            self.contains_msg_key(msg, ('command_id', 'length'))

            if msg['command_id'] not in self.command_id_to_reader_map:
                raise KeyError('unknown "command_id"')

            file_reader = self.command_id_to_reader_map[msg['command_id']]
            yield file_reader.remote_read(msg['length'])
        except Exception as e:
            is_exception = True
            result = str(e)
        self.send_response_msg(msg, result, is_exception)

    @defer.inlineCallbacks
    def call_update_read_file_close(self, msg):
        result = None
        is_exception = False
        try:
            self.contains_msg_key(msg, ('command_id',))

            if msg['command_id'] not in self.command_id_to_reader_map:
                raise KeyError('unknown "command_id"')

            file_reader = self.command_id_to_reader_map[msg['command_id']]
            yield file_reader.remote_close()
        except Exception as e:
            is_exception = True
            result = str(e)
        self.send_response_msg(msg, result, is_exception)

    @defer.inlineCallbacks
    def call_update_upload_directory_unpack(self, msg):
        result = None
        is_exception = False
        try:
            self.contains_msg_key(msg, ('command_id',))

            if msg['command_id'] not in self.command_id_to_writer_map:
                raise KeyError('unknown "command_id"')

            directory_writer = self.command_id_to_writer_map[msg['command_id']]
            yield directory_writer.remote_unpack()
        except Exception as e:
            is_exception = True
            result = str(e)
        self.send_response_msg(msg, result, is_exception)

    @defer.inlineCallbacks
    def call_update_upload_directory_write(self, msg):
        result = None
        is_exception = False
        try:
            self.contains_msg_key(msg, ('command_id', 'args'))

            if msg['command_id'] not in self.command_id_to_writer_map:
                raise KeyError('unknown "command_id"')

            directory_writer = self.command_id_to_writer_map[msg['command_id']]
            yield directory_writer.remote_write(msg['args'])
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

        self.maybe_log_master_to_worker_msg(dict_output)
        payload = msgpack.packb(dict_output, use_bin_type=True)

        self.sendMessage(payload, isBinary=True)

    def onMessage(self, payload, isBinary):
        if not isBinary:
            name = self.worker_name if self.worker_name is not None else '<???>'
            log.msg(f'Message type from worker {name} unsupported')
            return

        msg = msgpack.unpackb(payload, raw=False)
        self.maybe_log_worker_to_master_msg(msg)

        if 'seq_number' not in msg or 'op' not in msg:
            log.msg(f'Invalid message from worker: {msg}')
            return

        if msg['op'] != "response" and self.connection is None:
            self.send_response_msg(msg, "Worker not authenticated.", is_exception=True)
            return

        if msg['op'] == "update":
            self._deferwaiter.add(self.call_update(msg))
        elif msg['op'] == "update_upload_file_write":
            self._deferwaiter.add(self.call_update_upload_file_write(msg))
        elif msg['op'] == "update_upload_file_close":
            self._deferwaiter.add(self.call_update_upload_file_close(msg))
        elif msg['op'] == "update_upload_file_utime":
            self._deferwaiter.add(self.call_update_upload_file_utime(msg))
        elif msg['op'] == "update_read_file":
            self._deferwaiter.add(self.call_update_read_file(msg))
        elif msg['op'] == "update_read_file_close":
            self._deferwaiter.add(self.call_update_read_file_close(msg))
        elif msg['op'] == "update_upload_directory_unpack":
            self._deferwaiter.add(self.call_update_upload_directory_unpack(msg))
        elif msg['op'] == "update_upload_directory_write":
            self._deferwaiter.add(self.call_update_upload_directory_write(msg))
        elif msg['op'] == "complete":
            self._deferwaiter.add(self.call_complete(msg))
        elif msg['op'] == "response":
            seq_number = msg['seq_number']
            if "is_exception" in msg:
                self.seq_num_to_waiters_map[seq_number].errback(RemoteWorkerError(msg['result']))
            else:
                self.seq_num_to_waiters_map[seq_number].callback(msg['result'])
            # stop waiting for a response of this command
            del self.seq_num_to_waiters_map[seq_number]
        else:
            self.send_response_msg(msg, f"Command {msg['op']} does not exist.",
                                   is_exception=True)

    @defer.inlineCallbacks
    def get_message_result(self, msg):
        if msg['op'] != 'print' and msg['op'] != 'get_worker_info' and self.connection is None:
            raise ConnectioLostError("No worker connection")

        msg['seq_number'] = self.seq_number

        self.maybe_log_master_to_worker_msg(msg)

        object = msgpack.packb(msg, use_bin_type=True)
        d = defer.Deferred()
        self.seq_num_to_waiters_map[self.seq_number] = d

        self.seq_number = self.seq_number + 1
        self.sendMessage(object, isBinary=True)
        res1 = yield d
        return res1

    @defer.inlineCallbacks
    def onConnect(self, request):
        if self.debug:
            log.msg(f"Client connecting: {request.peer}")

        value = request.headers.get('authorization')
        if value is None:
            raise ConnectionDeny(401, "Unauthorized")

        try:
            username, password = decode_http_authorization_header(value)
        except Exception as e:
            raise ConnectionDeny(400, "Bad request") from e

        try:
            dispatcher = self.get_dispatcher()
            yield dispatcher.master.initLock.acquire()

            if username in dispatcher.users:
                pwd, _ = dispatcher.users[username]
                if pwd == password:
                    self.worker_name = username
                    authentication = True
                else:
                    authentication = False
            else:
                authentication = False
        except Exception as e:
            raise Exception("Internal error") from e
        finally:
            eventually(dispatcher.master.initLock.release)

        if not authentication:
            raise ConnectionDeny(401, "Unauthorized")

    def onClose(self, wasClean, code, reason):
        if self.debug:
            log.msg(f"WebSocket connection closed: {reason}")
        # stop waiting for the responses of all commands
        for d in self.seq_num_to_waiters_map.values():
            d.errback(ConnectioLostError("Connection lost"))
        self.seq_num_to_waiters_map.clear()

        if self.connection is not None:
            self.connection.detached(self)


class Dispatcher(BaseDispatcher):

    DUMMY_PORT = 1

    def __init__(self, config_portstr, portstr):
        super().__init__(portstr)
        try:
            port = int(config_portstr)
        except ValueError as e:
            raise ValueError(f'portstr unsupported: {config_portstr}') from e

        # Autobahn does not support zero port meaning to pick whatever port number is free, so
        # we work around this by setting the port to nonzero value and resetting the value once
        # the port is known. This is possible because Autobahn doesn't do anything with the port
        # during the listening setup.
        self._zero_port = port == 0
        if self._zero_port:
            port = self.DUMMY_PORT

        self.serverFactory = WebSocketServerFactory(f"ws://0.0.0.0:{port}")
        self.serverFactory.buildbot_dispatcher = self
        self.serverFactory.protocol = BuildbotWebSocketServerProtocol

    def start_listening_port(self):
        port = super().start_listening_port()
        if self._zero_port:
            # Check that websocket port is actually stored into the port attribute, as we're
            # relying on undocumented behavior.
            if self.serverFactory.port != self.DUMMY_PORT:
                raise Exception("Expected websocket port to be set to dummy port")
            self.serverFactory.port = port.getHost().port
        return port


class MsgManager(BaseManager):
    def __init__(self):
        super().__init__('msgmanager')

    dispatcher_class = Dispatcher
