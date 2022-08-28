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

import stat

from twisted.internet import defer
from twisted.python import log
from twisted.python.reflect import namedModule

from buildbot.pbutil import decode
from buildbot.process import remotecommand
from buildbot.util import deferwaiter
from buildbot.util import path_expand_user
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


class BasicRemoteCommand():
    # only has basic functions needed for remoteSetBuilderList in class Connection
    # when waiting for update messages
    def __init__(self, worker_name, expected_keys, error_msg):
        self.worker_name = worker_name
        self.update_results = {}
        self.expected_keys = expected_keys
        self.error_msg = error_msg
        self.d = defer.Deferred()

    def wait_until_complete(self):
        return self.d

    def remote_update_msgpack(self, args):
        # args is a list of tuples
        # first element of the tuple is a key, second element is a value
        for key, value in args:
            if key not in self.update_results:
                self.update_results[key] = value

    def remote_complete(self, args):
        if 'rc' not in self.update_results:
            self.d.errback(Exception(f"Worker {self.worker_name} reconfiguration or connection to "
                                     f"master failed. {self.error_msg}. 'rc' did not arrive."))
            return

        if self.update_results['rc'] != 0:
            self.d.errback(Exception(f"Worker {self.worker_name} reconfiguration or connection to "
                                     f"master failed. {self.error_msg}. Error number: "
                                     f"{self.update_results['rc']}"))
            return

        for key in self.expected_keys:
            if key not in self.update_results:
                self.d.errback(Exception(f"Worker {self.worker_name} reconfiguration or connection "
                                         f"to master failed. {self.error_msg} "
                                         f"Key '{key}' is missing."))
                return

        self.d.callback(None)


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
        self.protocol.transport.abortConnection()

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
        self.info = decode(info)

        worker_system = self.info.get("system", None)
        if worker_system == "nt":
            self.path_module = namedModule("ntpath")
            self.path_expanduser = path_expand_user.nt_expanduser
        else:
            # most everything accepts / as separator, so posix should be a reasonable fallback
            self.path_module = namedModule("posixpath")
            self.path_expanduser = path_expand_user.posix_expanduser
        return self.info

    def _set_worker_settings(self):
        # the lookahead here (`(?=.)`) ensures that `\r` doesn't match at the end
        # of the buffer
        # we also convert cursor control sequence to newlines
        # and ugly \b+ (use of backspace to implement progress bar)
        newline_re = r'(\r\n|\r(?=.)|\033\[u|\033\[[0-9]+;[0-9]+[Hf]|\033\[2J|\x08+)'
        return self.protocol.get_message_result({
            'op': 'set_worker_settings',
            'args': {'newline_re': newline_re,
                     'max_line_length': 4096,
                     'buffer_timeout': 5,
                     'buffer_size': 64 * 1024}})

    def create_remote_command(self, worker_name, expected_keys, error_msg):
        command_id = remotecommand.RemoteCommand.generate_new_command_id()
        command = BasicRemoteCommand(worker_name, expected_keys, error_msg)
        self.protocol.command_id_to_command_map[command_id] = command
        return (command, command_id)

    @defer.inlineCallbacks
    def remoteSetBuilderList(self, builders):
        yield self._set_worker_settings()

        basedir = self.info['basedir']
        builder_names = [name for name, _ in builders]
        self.builder_basedirs = {name: self.path_module.join(basedir, builddir)
                                 for name, builddir in builders}

        wanted_dirs = {builddir for _, builddir in builders}
        wanted_dirs.add('info')
        dirs_to_mkdir = set(wanted_dirs)
        command, command_id = \
            self.create_remote_command(self.worker.workername, ['files'],
                                       'Worker could not send a list of builder directories.')

        yield self.protocol.get_message_result({'op': 'start_command',
                                                'command_id': command_id,
                                                'command_name': 'listdir',
                                                'args': {'path': basedir}})

        # wait until command is over to get the update request message with args['files']
        yield command.wait_until_complete()
        files = command.update_results['files']

        paths_to_rmdir = []

        for dir in files:
            dirs_to_mkdir.discard(dir)
            if dir not in wanted_dirs:
                if self.info['delete_leftover_dirs']:
                    # send 'stat' start_command and wait for status information which comes from
                    # worker in a response message. Status information is saved in update_results
                    # dictionary with key 'stat'. 'stat' value is a tuple of 10 elements, where
                    # first element is File mode. It goes to S_ISDIR(mode) to check if path is
                    # a directory so that files are not deleted
                    path = self.path_module.join(basedir, dir)
                    command, command_id = \
                        self.create_remote_command(self.worker.workername, ['stat'],
                                                   "Worker could not send status " +
                                                   "information about its files.")
                    yield self.protocol.get_message_result({'op': 'start_command',
                                                            'command_id': command_id,
                                                            'command_name': 'stat',
                                                            'args': {'path': path}})
                    yield command.wait_until_complete()
                    mode = command.update_results['stat'][0]
                    if stat.S_ISDIR(mode):
                        paths_to_rmdir.append(path)

        if paths_to_rmdir:
            log.msg(f"Deleting directory '{paths_to_rmdir}' that is not being "
                    "used by the buildmaster.")

            # remove leftover directories from worker
            command, command_id = \
                self.create_remote_command(self.worker.workername, [],
                                           "Worker could not remove directories.")
            yield self.protocol.get_message_result({'op': 'start_command',
                                                    'command_id': command_id,
                                                    'command_name': 'rmdir',
                                                    'args': {'paths': paths_to_rmdir}})
            yield command.wait_until_complete()

        paths_to_mkdir = [self.path_module.join(basedir, dir)
                          for dir in sorted(list(dirs_to_mkdir))]
        if paths_to_mkdir:
            # make wanted builder directories which do not exist in worker yet
            command, command_id = self.create_remote_command(self.worker.workername, [],
                                                             "Worker could not make directories.")
            yield self.protocol.get_message_result({'op': 'start_command',
                                                    'command_id': command_id,
                                                    'command_name': 'mkdir',
                                                    'args': {'paths': paths_to_mkdir}})
            yield command.wait_until_complete()

        self.builders = builder_names
        return builder_names

    @defer.inlineCallbacks
    def remoteStartCommand(self, remoteCommand, builderName, commandId, commandName, args):
        if commandName == "mkdir":
            if isinstance(args['dir'], list):
                args['paths'] = [self.path_module.join(self.builder_basedirs[builderName], dir)
                                 for dir in args['dir']]
            else:
                args['paths'] = [self.path_module.join(self.builder_basedirs[builderName],
                                                       args['dir'])]
            del args['dir']

        if commandName == "rmdir":
            if isinstance(args['dir'], list):
                args['paths'] = [self.path_module.join(self.builder_basedirs[builderName], dir)
                                 for dir in args['dir']]
            else:
                args['paths'] = [self.path_module.join(self.builder_basedirs[builderName],
                                                       args['dir'])]
            del args['dir']

        if commandName == "cpdir":
            args['from_path'] = self.path_module.join(self.builder_basedirs[builderName],
                                                      args['fromdir'])
            args['to_path'] = self.path_module.join(self.builder_basedirs[builderName],
                                                    args['todir'])
            del args['fromdir']
            del args['todir']

        if commandName == "stat":
            args['path'] = self.path_module.join(self.builder_basedirs[builderName],
                                                 args.get('workdir', ''), args['file'])
            del args['file']

        if commandName == "glob":
            args['path'] = self.path_module.join(self.builder_basedirs[builderName], args['path'])

        if commandName == "listdir":
            args['path'] = self.path_module.join(self.builder_basedirs[builderName], args['dir'])
            del args['dir']

        if commandName == "rmfile":
            args['path'] = self.path_module.join(self.builder_basedirs[builderName], args['path'])

        if commandName == "shell":
            args['workdir'] = self.path_module.join(self.builder_basedirs[builderName],
                                                    args['workdir'])

        if commandName == "uploadFile":
            commandName = "upload_file"
            args['path'] = self.path_module.join(self.builder_basedirs[builderName],
                                                 args['workdir'],
                                                 self.path_expanduser(args['workersrc'],
                                                                      self.info['environ']))

        if commandName == "uploadDirectory":
            commandName = "upload_directory"
            args['path'] = self.path_module.join(self.builder_basedirs[builderName],
                                                 args['workdir'],
                                                 self.path_expanduser(args['workersrc'],
                                                                      self.info['environ']))

        if commandName == "downloadFile":
            commandName = "download_file"
            args['path'] = self.path_module.join(self.builder_basedirs[builderName],
                                                 args['workdir'],
                                                 self.path_expanduser(args['workerdest'],
                                                                      self.info['environ']))
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

    def get_peer(self):
        p = self.protocol.transport.getPeer()
        return f"{p.host}:{p.port}"
