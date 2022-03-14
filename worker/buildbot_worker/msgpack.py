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
from twisted.application import service
from twisted.internet import defer
from twisted.python import log

from buildbot_worker.base import ProtocolCommandBase
from buildbot_worker.base import WorkerForBuilderBase
from buildbot_worker.pbutil import decode
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
        if (command in ("uploadDirectory", "uploadFile")) and 'writer' not in args:
            args['writer'] = None
        if command == "downloadFile" and 'reader' not in args:
            args['reader'] = None

    # Returns a Deferred
    def protocol_update(self, updates):
        protocol, commandId = self.command_ref
        return protocol.get_message_result({'op': 'update', 'args': updates,
                                            'command_id': commandId})

    def protocol_notify_on_disconnect(self):
        pass

    # Returns a Deferred
    def protocol_complete(self, failure):
        if failure is not None:
            failure = str(failure)
        protocol, commandId = self.command_ref
        return protocol.get_message_result({'op': 'complete', 'args': failure,
                                            'command_id': commandId})

    # Returns a Deferred
    def protocol_update_upload_file_close(self, writer):
        protocol, commandId = self.command_ref
        return protocol.get_message_result({'op': 'update_upload_file_close',
                                            'command_id': commandId})

    # Returns a Deferred
    def protocol_update_upload_file_utime(self, writer, access_time, modified_time):
        protocol, commandId = self.command_ref
        return protocol.get_message_result({'op': 'update_upload_file_utime',
                                            'access_time': access_time,
                                            'modified_time': modified_time,
                                            'command_id': commandId})

    # Returns a Deferred
    def protocol_update_upload_file_write(self, writer, data):
        protocol, commandId = self.command_ref
        return protocol.get_message_result({'op': 'update_upload_file_write', 'args': data,
                                            'command_id': commandId})

    # Returns a Deferred
    def protocol_update_upload_directory(self, writer):
        protocol, commandId = self.command_ref
        return protocol.get_message_result({'op': 'update_upload_directory_unpack',
                                            'command_id': commandId})

    # Returns a Deferred
    def protocol_update_upload_directory_write(self, writer, data):
        protocol, commandId = self.command_ref
        return protocol.get_message_result({'op': 'update_upload_directory_write', 'args': data,
                                            'command_id': commandId})

    # Returns a Deferred
    def protocol_update_read_file_close(self, reader):
        protocol, commandId = self.command_ref
        return protocol.get_message_result({'op': 'update_read_file_close',
                                            'command_id': commandId})

    # Returns a Deferred
    def protocol_update_read_file(self, reader, length):
        protocol, commandId = self.command_ref
        return protocol.get_message_result({'op': 'update_read_file', 'length': length,
                                            'command_id': commandId})


class WorkerForBuilderMsgpack(WorkerForBuilderBase):
    ProtocolCommand = ProtocolCommandMsgpack

    """This is the local representation of a single Builder: it handles a
    single kind of build (like an all-warnings build). It has a name and a
    home directory. The rest of its behavior is determined by the master.
    """

    # remote is a ref to the Builder object on the master side, and is set
    # when they attach. We use it to detect when the connection to the master
    # is severed.
    remote = None

    def __init__(self, name, unicode_encoding):
        # service.Service.__init__(self) # Service has no __init__ method
        self.setName(name)
        self.unicode_encoding = unicode_encoding
        self.protocol_command = None

    def __repr__(self):
        return "<WorkerForBuilder '{0}' at {1}>".format(self.name, id(self))

    def startService(self):
        service.Service.startService(self)
        if self.protocol_command:
            self.protocol_command.builder_is_running = True

    def stopService(self):
        service.Service.stopService(self)
        if self.protocol_command:
            self.protocol_command.builder_is_running = False
        self.stopCommand()

    def remote_setMaster(self, remote):
        self.remote = remote
        self.remote.notifyOnDisconnect(self.lostRemote)

    def remote_print(self, message):
        log.msg("WorkerForBuilder.remote_print({0}): message from master: {1}".format(
                self.name, message))

    def lostRemote(self, remote):
        log.msg("lost remote")
        self.remote = None

    def lostRemoteStep(self, remotestep):
        log.msg("lost remote step")
        self.protocol_command.command_ref = None
        self.stopCommand()

    # the following are Commands that can be invoked by the master-side
    # Builder
    def remote_startBuild(self):
        """This is invoked before the first step of any new build is run.  It
        doesn't do much, but masters call it so it's still here."""

    def remote_startCommand(self, command_ref, stepId, command, args):
        """
        This gets invoked by L{buildbot.process.step.RemoteCommand.start}, as
        part of various master-side BuildSteps, to start various commands
        that actually do the build. I return nothing. Eventually I will call
        .commandComplete() to notify the master-side RemoteCommand that I'm
        done.
        """
        stepId = decode(stepId)
        command = decode(command)
        args = decode(args)

        if self.protocol_command:
            log.msg("leftover command, dropping it")
            self.stopCommand()

        def on_command_complete():
            self.protocol_command = None

        self.protocol_command = self.ProtocolCommand(self.unicode_encoding, self.basedir,
                                                     self.running, on_command_complete,
                                                     self.lostRemoteStep, command, stepId, args,
                                                     command_ref)

        log.msg(u" startCommand:{0} [id {1}]".format(command, stepId))
        self.protocol_command.protocol_notify_on_disconnect()
        d = self.protocol_command.command.doStart()
        d.addCallback(lambda res: None)
        d.addBoth(self.protocol_command.command_complete)
        return None

    def remote_interruptCommand(self, stepId, why):
        """Halt the current step."""
        log.msg("asked to interrupt current command: {0}".format(why))
        if not self.protocol_command:
            # TODO: just log it, a race could result in their interrupting a
            # command that wasn't actually running
            log.msg(" .. but none was running")
            return
        self.protocol_command.command.doInterrupt()

    def stopCommand(self):
        """Make any currently-running command die, with no further status
        output. This is used when the worker is shutting down or the
        connection to the master has been lost. Interrupt the command,
        silence it, and then forget about it."""
        if not self.protocol_command:
            return
        log.msg("stopCommand: halting current command {0}".format(self.protocol_command.command))
        self.protocol_command.command.doInterrupt()
        self.protocol_command = None


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

    @defer.inlineCallbacks
    def call_set_builder_list(self, msg):
        is_exception = False
        try:
            self.contains_msg_key(msg, ('builders',))
            result = yield self.factory.buildbot_bot.remote_setBuilderList(msg["builders"])
        except Exception as e:
            is_exception = True
            result = str(e)

        self.send_response_msg(msg, result, is_exception)

    @defer.inlineCallbacks
    def call_start_command(self, msg):
        is_exception = False
        try:
            self.contains_msg_key(msg, ('builder_name', 'command_id', 'command_name', 'args'))
            builder_name = msg['builder_name']
            worker_for_builder = self.factory.buildbot_bot.builders[builder_name]
            # send an instance, on which get_message_result will be called
            command_ref = (self, msg['command_id'])
            yield worker_for_builder.remote_startCommand(command_ref, msg['command_id'],
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
            self.contains_msg_key(msg, ('builder_name', 'command_id', 'why'))
            builder_name = msg['builder_name']
            worker_for_builder = self.factory.buildbot_bot.builders[builder_name]
            # send an instance, on which get_message_result will be called
            yield worker_for_builder.remote_interruptCommand(msg['command_id'],
                                                             msg['why'])
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
        elif msg['op'] == "get_worker_info":
            self._deferwaiter.add(self.call_get_worker_info(msg))
        elif msg['op'] == "set_builder_list":
            self._deferwaiter.add(self.call_set_builder_list(msg))
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
