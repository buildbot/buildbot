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

from buildbot.util import ComparableMixin
from buildbot.util import subscription
from buildbot.util.eventual import eventually


class Listener:
    pass


class UpdateRegistrationListener(Listener):
    def __init__(self):
        super().__init__()
        # username : (password, portstr, manager registration)
        self._registrations = {}

    @defer.inlineCallbacks
    def updateRegistration(self, username, password, portStr):
        # NOTE: this method is only present on the PB and MsgPack protocols; others do not
        # use registrations
        if username in self._registrations:
            currentPassword, currentPortStr, currentReg = \
                self._registrations[username]
        else:
            currentPassword, currentPortStr, currentReg = None, None, None

        iseq = (ComparableMixin.isEquivalent(currentPassword, password) and
                ComparableMixin.isEquivalent(currentPortStr, portStr))
        if iseq:
            return currentReg
        if currentReg:
            yield currentReg.unregister()
            del self._registrations[username]

        if portStr is not None and password:
            reg = yield self.get_manager().register(portStr, username, password,
                                                    self._create_connection)
            self._registrations[username] = (password, portStr, reg)
            return reg
        return currentReg

    @defer.inlineCallbacks
    def _create_connection(self, mind, workerName):
        self.before_connection_setup(mind, workerName)
        worker = self.master.workers.getWorkerByName(workerName)
        conn = self.ConnectionClass(self.master, worker, mind)

        # inform the manager, logging any problems in the deferred
        accepted = yield self.master.workers.newConnection(conn, workerName)

        # return the Connection as the perspective
        if accepted:
            return conn
        else:
            # TODO: return something more useful
            raise RuntimeError("rejecting duplicate worker")


class Connection:
    proxies = {}

    def __init__(self, name):
        self._disconnectSubs = subscription.SubscriptionPoint(f"disconnections from {name}")

    # This method replace all Impl args by their Proxy protocol implementation
    def createArgsProxies(self, args):
        newargs = {}
        for k, v in args.items():
            for implclass, proxyclass in self.proxies.items():
                if isinstance(v, implclass):
                    v = proxyclass(v)
            newargs[k] = v
        return newargs

    def get_peer(self):
        raise NotImplementedError

    # disconnection handling

    def wait_shutdown_started(self):
        d = defer.Deferred()
        self.notifyOnDisconnect(lambda: eventually(d.callback, None))
        return d

    def waitShutdown(self):
        return self._disconnectSubs.waitForDeliveriesToFinish()

    def notifyOnDisconnect(self, cb):
        return self._disconnectSubs.subscribe(cb)

    def notifyDisconnected(self):
        self._disconnectSubs.deliver()

    def loseConnection(self):
        raise NotImplementedError

    # methods to send messages to the worker

    def remotePrint(self, message):
        raise NotImplementedError

    def remoteGetWorkerInfo(self):
        raise NotImplementedError

    def remoteSetBuilderList(self, builders):
        raise NotImplementedError

    def remoteStartCommand(self, remoteCommand, builderName, commandId, commandName, args):
        raise NotImplementedError

    def remoteShutdown(self):
        raise NotImplementedError

    def remoteStartBuild(self, builderName):
        raise NotImplementedError

    def remoteInterruptCommand(self, builderName, commandId, why):
        raise NotImplementedError


# RemoteCommand base implementation and base proxy
class RemoteCommandImpl:

    def remote_update(self, updates):
        raise NotImplementedError

    def remote_complete(self, failure=None):
        raise NotImplementedError


# FileWriter base implementation
class FileWriterImpl:

    def remote_write(self, data):
        raise NotImplementedError

    def remote_utime(self, accessed_modified):
        raise NotImplementedError

    def remote_unpack(self):
        raise NotImplementedError

    def remote_close(self):
        raise NotImplementedError


# FileReader base implementation
class FileReaderImpl:

    def remote_read(self, maxLength):
        raise NotImplementedError

    def remote_close(self):
        raise NotImplementedError
