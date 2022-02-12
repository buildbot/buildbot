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

from twisted.internet import defer
from twisted.python import log

from buildbot.pbutil import decode
from buildbot.util import deferwaiter
from buildbot.worker.protocols import base


class Listener(base.UpdateRegistrationListener):
    name = "MsgPackListener"

    def __init__(self, master):
        super().__init__()
        self.ConnectionClass = Connection
        self.master = master

    def get_manager(self):
        return self.master.msgmanager

    def before_connection_setup(self, protocol, workerName):
        log.msg(f"worker '{workerName}' attaching")


class Connection(base.Connection):
    # TODO: configure keepalive_interval in
    # c['protocols']['msgpack']['keepalive_interval']
    keepalive_timer = None
    keepalive_interval = 3600
    info = None

    def __init__(self, master, worker, protocol):
        super().__init__(worker.workername)
        self.master = master
        self.worker = worker
        self.protocol = protocol
        self._keepalive_waiter = deferwaiter.DeferWaiter()
        self._keepalive_action_handler = \
            deferwaiter.RepeatedActionHandler(master.reactor, self._keepalive_waiter,
                                              self.keepalive_interval, self._do_keepalive)

    # methods called by the BuildbotWebSocketServerProtocol

    @defer.inlineCallbacks
    def attached(self, protocol):
        self.startKeepaliveTimer()
        self.notifyOnDisconnect(self._stop_keepalive_timer)
        yield self.worker.attached(self)

    def detached(self, protocol):
        self.stopKeepaliveTimer()
        self.protocol = None
        self.notifyDisconnected()

    # disconnection handling
    @defer.inlineCallbacks
    def _stop_keepalive_timer(self):
        self.stopKeepaliveTimer()
        yield self._keepalive_waiter.wait()

    def loseConnection(self):
        self.stopKeepaliveTimer()
        self.protocol.sendClose()

    # keepalive handling

    def _do_keepalive(self):
        return self.remoteKeepalive()

    def stopKeepaliveTimer(self):
        self._keepalive_action_handler.stop()

    def startKeepaliveTimer(self):
        assert self.keepalive_interval
        self._keepalive_action_handler.start()

    # methods to send messages to the worker

    def remoteKeepalive(self):
        return self.protocol.get_message_result({'op': 'keepalive'})

    def remotePrint(self, message):
        return self.protocol.get_message_result({'op': 'print', 'message': message})

    @defer.inlineCallbacks
    def remoteGetWorkerInfo(self):
        info = yield self.protocol.get_message_result({'op': 'get_worker_info'})
        return decode(info)

    @defer.inlineCallbacks
    def remoteSetBuilderList(self, builders):
        builders = yield self.protocol.get_message_result({'op': 'set_builder_list',
                                                           'builders': builders})
        self.builders = decode(builders)
        return builders

    @defer.inlineCallbacks
    def remoteStartCommand(self, remoteCommand, builderName, commandId, commandName, args):
        if "want_stdout" in args:
            if args["want_stdout"] == 1:
                args["want_stdout"] = True
            else:
                args["want_stdout"] = False

        if "want_stderr" in args:
            if args["want_stderr"] == 1:
                args["want_stderr"] = True
            else:
                args["want_stderr"] = False

        self.protocol.command_id_to_command_map[commandId] = remoteCommand
        if 'reader' in args:
            self.protocol.command_id_to_reader_map[commandId] = args['reader']
            del args['reader']
        if 'writer' in args:
            self.protocol.command_id_to_writer_map[commandId] = args['writer']
            del args['writer']
        yield self.protocol.get_message_result({'op': 'start_command', 'builder_name': builderName,
                                               'command_id': commandId, 'command_name': commandName,
                                               'args': args})

    @defer.inlineCallbacks
    def remoteShutdown(self):
        yield self.protocol.get_message_result({'op': 'shutdown'})

    def remoteStartBuild(self, builderName):
        pass

    @defer.inlineCallbacks
    def remoteInterruptCommand(self, builderName, commandId, why):
        yield self.protocol.get_message_result({'op': 'interrupt_command',
                                               'builder_name': builderName, 'command_id': commandId,
                                               'why': why})

    # perspective methods called by the worker

    def perspective_keepalive(self):
        self.worker.messageReceivedFromWorker()

    def perspective_shutdown(self):
        self.worker.messageReceivedFromWorker()
        self.worker.shutdownRequested()
