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

from twisted.python import log
from twisted.internet import defer, reactor
from buildbot.buildslave.protocols import base
from twisted.spread import pb

class Listener(base.Listener):

    def __init__(self, master):
        base.Listener.__init__(self, master)

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
            if portStr:
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

class Connection(base.Connection, pb.Avatar):

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
        self.mind.broker.transport.loseConnection()

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
        except pb.NoSuchMethod, e:
            log.msg("BuildSlave.info_unavailable")
            log.msg(e)

        try:
            info["slave_commands"] = yield self.mind.callRemote('getCommands')
        except pb.NoSuchMethod, e:
            log.msg("BuildSlave.getCommands is unavailable - ignoring")

        try:
            info["version"] = yield self.mind.callRemote('getVersion')
        except pb.NoSuchMethod:
            log.msg("BuildSlave.getVersion is unavailable - ignoring")

        defer.returnValue(info)

    def remoteSetBuilderList(self, builders):
        def cache_builders(builders):
            self.builders = builders
            return builders
        d = self.mind.callRemote('setBuilderList', builders)
        d.addCallback(cache_builders)
        return d

    def startCommands(self, remoteCommand, builderName, commandId, commandName, args):
        slavebuilder = self.builders.get(builderName)
        return slavebuilder.callRemote('startCommand',
            remoteCommand, commandId, commandName, args
        )

    @defer.inlineCallbacks
    def remoteShutdown(self):
        # First, try the "new" way - calling our own remote's shutdown
        # method. The method was only added in 0.8.3, so ignore NoSuchMethod
        # failures.
        def new_way():
            d = self.mind.callRemote('shutdown')
            d.addCallback(lambda _ : True) # successful shutdown request
            def check_nsm(f):
                f.trap(pb.NoSuchMethod)
                return False # fall through to the old way
            d.addErrback(check_nsm)
            def check_connlost(f):
                f.trap(pb.PBConnectionLost)
                return True # the slave is gone, so call it finished
            d.addErrback(check_connlost)
            return d

        if (yield new_way()):
            return # done!

        # Now, the old way. Look for a builder with a remote reference to the
        # client side slave. If we can find one, then call "shutdown" on the
        # remote builder, which will cause the slave buildbot process to exit.
        def old_way():
            d = None
            for b in self.buildslave.slavebuilders.values():
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
                def _errback(why):
                    if why.check(pb.PBConnectionLost):
                        log.msg("Lost connection to %s" % name)
                    else:
                        log.err("Unexpected error when trying to shutdown %s"
                                                                        % name)
                d.addErrback(_errback)
                return d
            log.err("Couldn't find remote builder to shut down slave")
            return defer.succeed(None)
        yield old_way()

    def remoteStartBuild(self, builderName):
        slavebuilder = self.builders.get(builderName)
        return slavebuilder.callRemote('startBuild')

    def remoteInterruptCommand(self, commandId, why):
        return defer.maybeDeferred(self.mind.callRemote, "interruptCommand",
            commandId, why)

    # perspective methods called by the slave

    def perspective_keepalive(self):
        self.buildslave.messageReceivedFromSlave()

    def perspective_shutdown(self):
        self.buildslave.messageReceivedFromSlave()
        self.buildslave.shutdownRequested()
