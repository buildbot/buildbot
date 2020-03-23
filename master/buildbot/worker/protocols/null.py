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

from buildbot.util.eventual import fireEventually
from buildbot.worker.protocols import base


class Listener(base.Listener):
    pass


class ProxyMixin():

    def __init__(self, impl):
        assert isinstance(impl, self.ImplClass)
        self.impl = impl
        self._disconnect_listeners = []

    def callRemote(self, message, *args, **kw):
        method = getattr(self.impl, "remote_{}".format(message), None)
        if method is None:
            raise AttributeError("No such method: remote_{}".format(message))
        try:
            state = method(*args, **kw)
        except TypeError:
            log.msg("{} didn't accept {} and {}".format(method, args, kw))
            raise
        # break callback recursion for large transfers by using fireEventually
        return fireEventually(state)

    def notifyOnDisconnect(self, cb):
        pass

    def dontNotifyOnDisconnect(self, cb):
        pass


# just add ProxyMixin capability to the RemoteCommandProxy
# so that callers of callRemote actually directly call the proper method
class RemoteCommandProxy(ProxyMixin):
    ImplClass = base.RemoteCommandImpl


class FileReaderProxy(ProxyMixin):
    ImplClass = base.FileReaderImpl


class FileWriterProxy(ProxyMixin):
    ImplClass = base.FileWriterImpl


class Connection(base.Connection):
    proxies = {base.FileWriterImpl: FileWriterProxy,
               base.FileReaderImpl: FileReaderProxy}

    def loseConnection(self):
        self.notifyDisconnected()

    def remotePrint(self, message):
        return defer.maybeDeferred(self.worker.bot.remote_print, message)

    def remoteGetWorkerInfo(self):
        return defer.maybeDeferred(self.worker.bot.remote_getWorkerInfo)

    def remoteSetBuilderList(self, builders):
        return defer.maybeDeferred(self.worker.bot.remote_setBuilderList, builders)

    def remoteStartCommand(self, remoteCommand, builderName, commandId, commandName, args):
        remoteCommand = RemoteCommandProxy(remoteCommand)
        args = self.createArgsProxies(args)
        workerforbuilder = self.worker.bot.builders[builderName]
        return defer.maybeDeferred(workerforbuilder.remote_startCommand, remoteCommand,
                                   commandId, commandName, args)

    def remoteShutdown(self):
        return defer.maybeDeferred(self.worker.stopService)

    def remoteStartBuild(self, builderName):
        return defer.succeed(self.worker.bot.builders[builderName].remote_startBuild())

    def remoteInterruptCommand(self, builderName, commandId, why):
        workerforbuilder = self.worker.bot.builders[builderName]
        return defer.maybeDeferred(workerforbuilder.remote_interruptCommand, commandId, why)
