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
from future.utils import itervalues

from buildbot.buildslave.protocols import base
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.spread import pb


class Listener(base.Listener):
    name = "pbListener"

    def __init__(self):
        base.Listener.__init__(self)

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
                reg = self.master.pbmanager.register(
                    portStr, username, password, self._getPerspective)
                self._registrations[username] = (password, portStr, reg)
                defer.returnValue(reg)

    @defer.inlineCallbacks
    def _getPerspective(self, mind, buildslaveName):
        bslaves = self.master.buildslaves
        log.msg("slave '%s' attaching from %s" % (buildslaveName,
                                                  mind.broker.transport.getPeer()))

        # try to use TCP keepalives
        try:
            mind.broker.transport.setTcpKeepAlive(1)
        except Exception:
            log.err("Can't set TcpKeepAlive")

        buildslave = bslaves.getBuildslaveByName(buildslaveName)
        conn = Connection(self.master, buildslave, mind)

        # inform the manager, logging any problems in the deferred
        accepted = yield bslaves.newConnection(conn, buildslaveName)

        # return the Connection as the perspective
        if accepted:
            defer.returnValue(conn)
        else:
            # TODO: return something more useful
            raise RuntimeError("rejecting duplicate slave")


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


class Connection(base.Connection, pb.Avatar):
    proxies = {base.FileWriterImpl: FileWriterProxy, base.FileReaderImpl: FileReaderProxy}
    # TODO: configure keepalive_interval in c['protocols']['pb']['keepalive_interval']
    keepalive_timer = None
    keepalive_interval = 3600
    info = None

    def __init__(self, master, buildslave, mind):
        base.Connection.__init__(self, master, buildslave)
        self.mind = mind

    # methods called by the PBManager

    @defer.inlineCallbacks
    def attached(self, mind):
        self.startKeepaliveTimer()
        # pbmanager calls perspective.attached; pass this along to the
        # buildslave
        yield self.buildslave.attached(self)
        # and then return a reference to the avatar
        defer.returnValue(self)

    def detached(self, mind):
        self.stopKeepaliveTimer()
        self.mind = None
        self.notifyDisconnected()

    # disconnection handling

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
            tport.dataBuffer = ""
        except Exception:
            # however, these hacks are pretty internal, so don't blow up if
            # they fail or are unavailable
            log.msg("failed to accelerate the shutdown process")

    # keepalive handling

    def doKeepalive(self):
        return self.mind.callRemote('print', message="keepalive")

    def stopKeepaliveTimer(self):
        if self.keepalive_timer and self.keepalive_timer.active():
            self.keepalive_timer.cancel()
            self.keepalive_timer = None

    def startKeepaliveTimer(self):
        assert self.keepalive_interval
        self.keepalive_timer = reactor.callLater(self.keepalive_interval,
                                                 self.doKeepalive)

    # methods to send messages to the slave

    def remotePrint(self, message):
        return self.mind.callRemote('print', message=message)

    @defer.inlineCallbacks
    def remoteGetSlaveInfo(self):
        info = {}
        try:
            info = yield self.mind.callRemote('getSlaveInfo')
        except pb.NoSuchMethod:
            log.msg("BuildSlave.getSlaveInfo is unavailable - ignoring")

        # newer slaves send all info in one command
        if "slave_commands" in info:
            defer.returnValue(info)
        try:
            info["slave_commands"] = yield self.mind.callRemote('getCommands')
        except pb.NoSuchMethod:
            log.msg("BuildSlave.getCommands is unavailable - ignoring")

        try:
            info["version"] = yield self.mind.callRemote('getVersion')
        except pb.NoSuchMethod:
            log.msg("BuildSlave.getVersion is unavailable - ignoring")

        defer.returnValue(info)

    def remoteSetBuilderList(self, builders):
        d = self.mind.callRemote('setBuilderList', builders)

        @d.addCallback
        def cache_builders(builders):
            self.builders = builders
            return builders
        return d

    def remoteStartCommand(self, remoteCommand, builderName, commandId, commandName, args):
        slavebuilder = self.builders.get(builderName)
        remoteCommand = RemoteCommand(remoteCommand)
        args = self.createArgsProxies(args)
        return slavebuilder.callRemote('startCommand',
                                       remoteCommand, commandId, commandName, args)

    @defer.inlineCallbacks
    def remoteShutdown(self):
        # First, try the "new" way - calling our own remote's shutdown
        # method. The method was only added in 0.8.3, so ignore NoSuchMethod
        # failures.
        def new_way():
            d = self.mind.callRemote('shutdown')
            d.addCallback(lambda _: True)  # successful shutdown request

            @d.addErrback
            def check_nsm(f):
                f.trap(pb.NoSuchMethod)
                return False  # fall through to the old way

            @d.addErrback
            def check_connlost(f):
                f.trap(pb.PBConnectionLost)
                return True  # the slave is gone, so call it finished
            return d

        if (yield new_way()):
            return  # done!

        # Now, the old way. Look for a builder with a remote reference to the
        # client side slave. If we can find one, then call "shutdown" on the
        # remote builder, which will cause the slave buildbot process to exit.
        def old_way():
            d = None
            for b in itervalues(self.buildslave.slavebuilders):
                if b.remote:
                    d = b.mind.callRemote("shutdown")
                    break

            if d:
                name = self.buildslave.slavename
                log.msg("Shutting down (old) slave: %s" % name)
                # The remote shutdown call will not complete successfully since
                # the buildbot process exits almost immediately after getting
                # the shutdown request.
                # Here we look at the reason why the remote call failed, and if
                # it's because the connection was lost, that means the slave
                # shutdown as expected.

                @d.addErrback
                def _errback(why):
                    if why.check(pb.PBConnectionLost):
                        log.msg("Lost connection to %s" % name)
                    else:
                        log.err("Unexpected error when trying to shutdown %s"
                                % name)
                return d
            log.err("Couldn't find remote builder to shut down slave")
            return defer.succeed(None)
        yield old_way()

    def remoteStartBuild(self, builderName):
        slavebuilder = self.builders.get(builderName)
        return slavebuilder.callRemote('startBuild')

    def remoteInterruptCommand(self, builderName, commandId, why):
        slavebuilder = self.builders.get(builderName)
        return defer.maybeDeferred(slavebuilder.callRemote, "interruptCommand",
                                   commandId, why)

    # perspective methods called by the slave

    def perspective_keepalive(self):
        self.buildslave.messageReceivedFromSlave()

    def perspective_shutdown(self):
        self.buildslave.messageReceivedFromSlave()
        self.buildslave.shutdownRequested()
