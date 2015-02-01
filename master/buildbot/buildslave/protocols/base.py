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

from buildbot.util import service
from buildbot.util import subscription


class Listener(service.ReconfigurableServiceMixin, service.AsyncMultiService):

    def __init__(self, master):
        service.AsyncMultiService.__init__(self)
        self.master = master


class Connection(object):
    proxies = {}

    def __init__(self, master, buildslave):
        self.master = master
        self.buildslave = buildslave
        name = buildslave.slavename
        self._disconnectSubs = subscription.SubscriptionPoint(
            "disconnections from %s" % name)

    # This method replace all Impl args by their Proxy protocol implementation
    def createArgsProxies(self, args):
        newargs = {}
        for k, v in args.iteritems():
            for implclass, proxyclass in self.proxies.items():
                if isinstance(v, implclass):
                    v = proxyclass(v)
            newargs[k] = v
        return newargs
    # disconnection handling

    def notifyOnDisconnect(self, cb):
        return self._disconnectSubs.subscribe(cb)

    def notifyDisconnected(self):
        self._disconnectSubs.deliver()

    def loseConnection(self):
        raise NotImplementedError

    # methods to send messages to the slave

    def remotePrint(self, message):
        raise NotImplementedError

    def remoteGetSlaveInfo(self):
        raise NotImplementedError

    def remoteSetBuilderList(self, builders):
        raise NotImplementedError

    def remoteStartCommand(self, remoteCommand, builderName, commandId, commandName, args):
        raise NotImplementedError

    def remoteShutdown(self):
        raise NotImplementedError

    def remoteStartBuild(self, builderName):
        raise NotImplementedError

    def remoteInterruptCommand(self, commandId, why):
        raise NotImplementedError


# RemoteCommand base implementation and base proxy


class RemoteCommandImpl(object):

    def remote_update(self, updates):
        raise NotImplementedError

    def remote_complete(self, failure=None):
        raise NotImplementedError


class RemoteCommandProxy(object):

    def __init__(self, impl):
        assert isinstance(impl, RemoteCommandImpl)
        self.impl = impl

    def remote_update(self, updates):
        return self.impl.remote_update(updates)

    def remote_complete(self, failure=None):
        return self.impl.remote_complete(failure)


# FileWriter base implementation and base proxy

class FileWriterImpl(object):

    def remote_write(self, data):
        raise NotImplementedError

    def remote_utime(self, accessed_modified):
        raise NotImplementedError

    def remote_unpack(self):
        raise NotImplementedError

    def remote_close(self):
        raise NotImplementedError


class FileWriterProxy(object):

    def __init__(self, impl):
        assert isinstance(impl, FileWriterImpl)
        self.impl = impl

    def remote_write(self, data):
        return self.impl.remote_write(data)

    def remote_utime(self, accessed_modified):
        return self.impl.remote_utime(accessed_modified)

    def remote_unpack(self):
        return self.impl.remote_unpack()

    def remote_close(self):
        return self.impl.remote_close()

# FileReader base implementation and base proxy


class FileReaderImpl(object):

    def remote_read(self, maxLength):
        raise NotImplementedError

    def remote_close(self):
        raise NotImplementedError


class FileReaderProxy(object):

    def __init__(self, impl):
        assert isinstance(impl, FileReaderImpl)
        self.impl = impl

    def remote_read(self, maxLength):
        return self.impl.remote_read(maxLength)

    def remote_close(self):
        return self.impl.remote_close()
