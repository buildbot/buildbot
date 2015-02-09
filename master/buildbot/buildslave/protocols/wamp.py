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

import inspect

from autobahn.wamp.uri import Pattern
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


def slave_register(uri):
    """
    Decorator for WAMP slave procedure endpoints
    """
    def decorate(f):
        assert(callable(f))
        if not hasattr(f, '_slavewampuris'):
            f._slavewampuris = []
        f._slavewampuris.append(Pattern(uri, Pattern.URI_TARGET_ENDPOINT))
        return f
    return decorate


class Connection(base.Connection):

    def __init__(self, master, buildslave):
        base.Connection.__init__(self, master, buildslave)
        self.curCommands = {}
        self.wamp = self.master.wamp.service
        self.unregisters = None

    def call(self, meth, *args, **kw):
        return self.wamp.call("org.buildslave." + self.buildslave.slavename + "." + meth,
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

    def getRemoteCommand(self, commandid):
        # TODO: sanity checks
        rc = self.curCommands[commandid]
        return rc

    def findAllRegistrations(self):
        slavename = self.buildslave.slavename
        base = "org.buildbot." + slavename + "."
        test = lambda x: inspect.ismethod(x) or inspect.isfunction(x)
        for k in inspect.getmembers(self, test):
            proc = k[1]
            if "_slavewampuris" in proc.__dict__:
                pat = proc.__dict__["_slavewampuris"][0]
                if pat.is_endpoint():
                    uri = base + pat.uri()
                    yield (proc, uri)

    @defer.inlineCallbacks
    def attached(self):
        slavename = self.buildslave.slavename
        if self.unregisters is not None:
            yield self.detached()
        dl = []
        for proc, uri in self.findAllRegistrations():
            dl.append(self.wamp.register(proc, uri))

        self.unregisters = yield defer.gatherResults(dl)
        yield self.wamp.publish("org.buildslave." + slavename + ".attached", self.master.masterid)

    @defer.inlineCallbacks
    def detached(self):
        slavename = self.buildslave.slavename
        if self.unregisters is None:
            yield defer.gatherResults([unregister() for unregister in self.unregisters])
            self.unregisters = None
        yield self.wamp.publish("org.buildslave." + slavename + ".detached", self.master.masterid)

    @slave_register(u"remotecommand.update")
    def rc_update(self, commandid, updates):
        rc = self.getRemoteCommand(commandid)
        return rc.remoteCommand.remote_update(updates)

    @slave_register(u"remotecommand.complete")
    def rc_complete(self, commandid, failure=None):
        rc = self.getRemoteCommand(commandid)
        return rc.remoteCommand.remote_complete(failure)

    # FileWriter base implementation

    @slave_register(u"filewriter.write")
    def fw_write(self, commandid, data):
        rc = self.getRemoteCommand(commandid)
        return rc.filewriter.remote_write(data)

    @slave_register(u"filewriter.utime")
    def fw_utime(self, commandid, accessed_modified):
        rc = self.getRemoteCommand(commandid)
        return rc.filewriter.remote_utime(accessed_modified)

    @slave_register(u"filewriter.unpack")
    def fw_unpack(self, commandid):
        rc = self.getRemoteCommand(commandid)
        return rc.filewriter.remote_unpack()

    @slave_register(u"filewriter.close")
    def fw_close(self, commandid):
        rc = self.getRemoteCommand(commandid)
        return rc.filewriter.remote_close()

    # FileReader base implementation

    @slave_register(u"filereader.read")
    def fr_read(self, commandid, maxLength):
        rc = self.getRemoteCommand(commandid)
        return rc.filereader.remote_read(maxLength)

    @slave_register(u"filereader.close")
    def fr_close(self, commandid):
        rc = self.getRemoteCommand(commandid)
        return rc.filereader.remote_close()
