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

import contextlib

from twisted.internet import defer
from twisted.python import log
from twisted.spread import pb

from buildbot.pbutil import decode
from buildbot.util import deferwaiter
from buildbot.worker.protocols import base


class Listener(base.Listener):
    name = "pbListener"

    def __init__(self):
        super().__init__()

        # username : (password, portstr, PBManager registration)
        self._registrations = {}

    @defer.inlineCallbacks
    def updateRegistration(self, username, password, portStr):
        # NOTE: this method is only present on the PB protocol; others do not
        # use registrations
        if username in self._registrations:
            currentPassword, currentPortStr, currentReg = \
                self._registrations[username]
        else:
            currentPassword, currentPortStr, currentReg = None, None, None

        if currentPassword != password or currentPortStr != portStr:
            if currentReg:
                yield currentReg.unregister()
                del self._registrations[username]
            if portStr and password:
                reg = yield self.master.pbmanager.register(portStr, username, password,
                                                           self._getPerspective)
                self._registrations[username] = (password, portStr, reg)
                return reg

    @defer.inlineCallbacks
    def _getPerspective(self, mind, workerName):
        workers = self.master.workers
        log.msg("worker '%s' attaching from %s" % (workerName,
                                                   mind.broker.transport.getPeer()))

        # try to use TCP keepalives
        try:
            mind.broker.transport.setTcpKeepAlive(1)
        except Exception:
            log.err("Can't set TcpKeepAlive")

        worker = workers.getWorkerByName(workerName)
        conn = Connection(self.master, worker, mind)

        # inform the manager, logging any problems in the deferred
        accepted = yield workers.newConnection(conn, workerName)

        # return the Connection as the perspective
        if accepted:
            return conn
        else:
            # TODO: return something more useful
            raise RuntimeError("rejecting duplicate worker")


class ReferenceableProxy(pb.Referenceable):

    def __init__(self, impl):
        assert isinstance(impl, self.ImplClass)
        self.impl = impl

    def __getattr__(self, default=None):
        return getattr(self.impl, default)


# Proxy are just ReferenceableProxy to the Impl classes
class RemoteCommand(ReferenceableProxy):
    ImplClass = base.RemoteCommandImpl


class FileReaderProxy(ReferenceableProxy):
    ImplClass = base.FileReaderImpl


class FileWriterProxy(ReferenceableProxy):
    ImplClass = base.FileWriterImpl


class _NoSuchMethod(Exception):
    """Rewrapped pb.NoSuchMethod remote exception"""


@contextlib.contextmanager
def _wrapRemoteException():
    try:
        yield
    except pb.RemoteError as ex:
        if ex.remoteType in (b'twisted.spread.flavors.NoSuchMethod',
                             'twisted.spread.flavors.NoSuchMethod'):
            raise _NoSuchMethod(ex)
        raise


class Connection(base.Connection, pb.Avatar):
    proxies = {base.FileWriterImpl: FileWriterProxy,
               base.FileReaderImpl: FileReaderProxy}
    # TODO: configure keepalive_interval in
    # c['protocols']['pb']['keepalive_interval']
    keepalive_timer = None
    keepalive_interval = 3600
    info = None

    def __init__(self, master, worker, mind):
        super().__init__(master, worker)
        self.mind = mind
        self._keepalive_waiter = deferwaiter.DeferWaiter()
        self._keepalive_action_handler = \
            deferwaiter.RepeatedActionHandler(master.reactor, self._keepalive_waiter,
                                              self.keepalive_interval, self._do_keepalive)

    # methods called by the PBManager

    @defer.inlineCallbacks
    def attached(self, mind):
        self.startKeepaliveTimer()
        # pbmanager calls perspective.attached; pass this along to the
        # worker
        yield self.worker.attached(self)
        # and then return a reference to the avatar
        return self

    def detached(self, mind):
        self.stopKeepaliveTimer()
        self.mind = None
        self.notifyDisconnected()

    # disconnection handling
    @defer.inlineCallbacks
    def waitShutdown(self):
        self.stopKeepaliveTimer()
        yield self._keepalive_waiter.wait()

    def loseConnection(self):
        self.stopKeepaliveTimer()
        tport = self.mind.broker.transport
        # this is the polite way to request that a socket be closed
        tport.loseConnection()
        try:
            # but really we don't want to wait for the transmit queue to
            # drain. The remote end is unlikely to ACK the data, so we'd
            # probably have to wait for a (20-minute) TCP timeout.
            # tport._closeSocket()
            # however, doing _closeSocket (whether before or after
            # loseConnection) somehow prevents the notifyOnDisconnect
            # handlers from being run. Bummer.
            tport.offset = 0
            tport.dataBuffer = b""
        except Exception:
            # however, these hacks are pretty internal, so don't blow up if
            # they fail or are unavailable
            log.msg("failed to accelerate the shutdown process")

    # keepalive handling

    def _do_keepalive(self):
        return self.mind.callRemote('print', message="keepalive")

    def stopKeepaliveTimer(self):
        self._keepalive_action_handler.stop()

    def startKeepaliveTimer(self):
        assert self.keepalive_interval
        self._keepalive_action_handler.start()

    # methods to send messages to the worker

    def remotePrint(self, message):
        return self.mind.callRemote('print', message=message)

    @defer.inlineCallbacks
    def remoteGetWorkerInfo(self):
        try:
            with _wrapRemoteException():
                # Try to call buildbot-worker method.
                info = yield self.mind.callRemote('getWorkerInfo')
            return decode(info)
        except _NoSuchMethod:
            yield self.remotePrint(
                "buildbot-slave detected, failing back to deprecated buildslave API. "
                "(Ignoring missing getWorkerInfo method.)")
            info = {}

            # Probably this is deprecated buildslave.
            log.msg("Worker.getWorkerInfo is unavailable - falling back to "
                    "deprecated buildslave API")

            try:
                with _wrapRemoteException():
                    info = yield self.mind.callRemote('getSlaveInfo')
            except _NoSuchMethod:
                log.msg("Worker.getSlaveInfo is unavailable - ignoring")

            # newer workers send all info in one command
            if "slave_commands" in info:
                assert "worker_commands" not in info
                info["worker_commands"] = info.pop("slave_commands")
                return info

            # Old version buildslave - need to retrieve list of supported
            # commands and version using separate requests.
            try:
                with _wrapRemoteException():
                    info["worker_commands"] = yield self.mind.callRemote(
                        'getCommands')
            except _NoSuchMethod:
                log.msg("Worker.getCommands is unavailable - ignoring")

            try:
                with _wrapRemoteException():
                    info["version"] = yield self.mind.callRemote('getVersion')
            except _NoSuchMethod:
                log.msg("Worker.getVersion is unavailable - ignoring")

            return decode(info)

    @defer.inlineCallbacks
    def remoteSetBuilderList(self, builders):
        builders = yield self.mind.callRemote('setBuilderList', builders)
        self.builders = builders
        return builders

    def remoteStartCommand(self, remoteCommand, builderName, commandId, commandName, args):
        workerforbuilder = self.builders.get(builderName)
        remoteCommand = RemoteCommand(remoteCommand)
        args = self.createArgsProxies(args)
        return workerforbuilder.callRemote('startCommand',
                                           remoteCommand, commandId, commandName, args)

    @defer.inlineCallbacks
    def remoteShutdown(self):
        # First, try the "new" way - calling our own remote's shutdown
        # method. The method was only added in 0.8.3, so ignore NoSuchMethod
        # failures.
        @defer.inlineCallbacks
        def new_way():
            try:
                with _wrapRemoteException():
                    yield self.mind.callRemote('shutdown')
                    # successful shutdown request
                    return True
            except _NoSuchMethod:
                # fall through to the old way
                return False

            except pb.PBConnectionLost:
                # the worker is gone, so call it finished
                return True

        if (yield new_way()):
            return  # done!

        # Now, the old way. Look for a builder with a remote reference to the
        # client side worker. If we can find one, then call "shutdown" on the
        # remote builder, which will cause the worker buildbot process to exit.
        def old_way():
            d = None
            for b in self.worker.workerforbuilders.values():
                if b.remote:
                    d = b.mind.callRemote("shutdown")
                    break

            if d:
                name = self.worker.workername
                log.msg("Shutting down (old) worker: %s" % name)
                # The remote shutdown call will not complete successfully since
                # the buildbot process exits almost immediately after getting
                # the shutdown request.
                # Here we look at the reason why the remote call failed, and if
                # it's because the connection was lost, that means the worker
                # shutdown as expected.

                @d.addErrback
                def _errback(why):
                    if why.check(pb.PBConnectionLost):
                        log.msg("Lost connection to %s" % name)
                    else:
                        log.err("Unexpected error when trying to shutdown %s"
                                % name)
                return d
            log.err("Couldn't find remote builder to shut down worker")
            return defer.succeed(None)
        yield old_way()

    def remoteStartBuild(self, builderName):
        workerforbuilder = self.builders.get(builderName)
        return workerforbuilder.callRemote('startBuild')

    def remoteInterruptCommand(self, builderName, commandId, why):
        workerforbuilder = self.builders.get(builderName)
        return defer.maybeDeferred(workerforbuilder.callRemote, "interruptCommand",
                                   commandId, why)

    # perspective methods called by the worker

    def perspective_keepalive(self):
        self.worker.messageReceivedFromWorker()

    def perspective_shutdown(self):
        self.worker.messageReceivedFromWorker()
        self.worker.shutdownRequested()
