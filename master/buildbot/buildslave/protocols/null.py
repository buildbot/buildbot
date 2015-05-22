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

from buildbot.buildslave.protocols import base
from twisted.internet import defer
from twisted.python import log


class Listener(base.Listener):
    pass


class ProxyMixin():

    def __init__(self, impl):
        assert isinstance(impl, self.ImplClass)
        self.impl = impl

    def callRemote(self, message, *args, **kw):
        method = getattr(self.impl, "remote_%s" % message, None)
        if method is None:
            raise AttributeError("No such method: remote_%s" % (message,))
        try:
            state = method(*args, **kw)
        except TypeError:
            log.msg("%s didn't accept %s and %s" % (method, args, kw))
            raise
        return defer.maybeDeferred(lambda: state)

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
    proxies = {base.FileWriterImpl: FileWriterProxy, base.FileReaderImpl: FileReaderProxy}

    def remotePrint(self, message):
        return defer.maybeDeferred(self.buildslave.bot.remote_print, message)

    def remoteGetSlaveInfo(self):
        return defer.maybeDeferred(self.buildslave.bot.remote_getSlaveInfo)

    def remoteSetBuilderList(self, builders):
        return defer.maybeDeferred(self.buildslave.bot.remote_setBuilderList, builders)

    def remoteStartCommand(self, remoteCommand, builderName, commandId, commandName, args):
        remoteCommand = RemoteCommandProxy(remoteCommand)
        args = self.createArgsProxies(args)
        slavebuilder = self.buildslave.bot.builders[builderName]
        return defer.maybeDeferred(slavebuilder.remote_startCommand, remoteCommand,
                                   commandId, commandName, args)

    def remoteShutdown(self):
        return defer.maybeDeferred(self.buildslave.stopService)

    def remoteStartBuild(self, builderName):
        return defer.succeed(self.buildslave.bot.builders[builderName].remote_startBuild())

    def remoteInterruptCommand(self, builderName, commandId, why):
        slavebuilder = self.buildslave.bot.builders[builderName]
        return defer.maybeDeferred(slavebuilder.remote_interruptCommand, commandId, why)
