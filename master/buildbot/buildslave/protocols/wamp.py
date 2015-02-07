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


# just add ProxyMixin capability to the RemoteCommandProxy
# so that callers of callRemote actually directly call the proper method
class RemoteCommandProxy(object):

    def __init__(self, remoteCommand, commandName, args):
        assert isinstance(remoteCommand, base.RemoteCommandImpl)
        self.remoteCommand = remoteCommand
        self.local_args = args
        self.remote_args = {}
        for k, v in args.iteritems():
            if isinstance(v, base.FileReaderImpl):
                self.filereader = v
                v = "FR" + str(id(v))  # anything but None will be proxied
            if isinstance(v, base.FileWriterImpl):
                self.filewriter = v
                v = "FW" + str(id(v))  # anything but None will be proxied
            self.remote_args[k] = v


class Connection(base.Connection):

    def __init__(self, master, buildslave):
        base.Connection.__init__(self, master, buildslave)
        self.curCommands = {}

    def call(self, meth, *args, **kw):
        return self.master.wamp.call("org.buildslave." + self.buildslave.slavename + "." + meth,
                                     *args, **kw)

    def remotePrint(self, message):
        return self.call("print", message)

    def remoteGetSlaveInfo(self):
        return self.call("getSlaveInfo")

    @defer.inlineCallbacks
    def remoteSetBuilderList(self, builders):
        yield self.call("setBuilderList", builders)
        defer.returnValue([name for name, path in builders])

    def remoteStartCommand(self, remoteCommand, builderName, commandId, commandName, args):
        self.curCommands[commandId] = RemoteCommandProxy(remoteCommand, commandName, args)
        args = self.curCommands[commandId].remote_args
        return self.call("startCommand", builderName, commandId, commandName, args)

    def remoteShutdown(self):
        return self.call("shutdown")

    def remoteStartBuild(self, builderName):
        # it is useless for slave version supported, so dont call it
        return defer.succeed(None)

    def remoteInterruptCommand(self, commandId, why):
        return self.call("interruptCommand", commandId, why)
