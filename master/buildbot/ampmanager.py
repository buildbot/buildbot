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

import pprint

from zope.interface import implements
from twisted.spread import pb
from twisted.python import failure, log
from twisted.internet import defer, reactor
from twisted.cred import portal, checkers, credentials, error
from twisted.application import service, strports
from twisted.internet.protocol import Factory

from buildbot.protocols import *

debug = True

class AMPManager(service.MultiService):
    def __init__(self):
        print "+++++++++ AMPManager.__init__"
        service.MultiService.__init__(self)
        self.setName('ampManager')
        self.ports = {}
        self.users = {}

    def register(self, portstr, username, password, pfactory):
        print "+++++++++ AMPManager.register", portstr
        reg = Registration(self, portstr, username)

        if portstr not in self.ports:
            if debug:
                log.msg('Trying to start AMP manager')
            pf = Factory()
            pf.protocol = lambda: Master(self)
            port = self.ports[portstr] = reactor.listenTCP(portstr, pf)
        else:
            port = self.ports[portstr]

        if debug:
            log.msg("registering username '%s' on port %s: %s"
                % (username, portstr, pfactory))
        if username in self.users:
            raise KeyError, ("username '%s' is already registered on port %s"
                             % (username, portstr))
        self.users[username] = (password, pfactory)
        return reg

    def _unregister(self, registration):
        print "+++++++++ AMPManager._unregister"
        portstr = registration.portstr
        username = registration.username
        if debug:
            log.msg("unregistering username '%s' on port %s" % (username, portstr))
        del self.users[username]
        registration.username = None
        if not self.users:
            port = self.ports[registration.portstr]
            del self.ports[registration.portstr]
            return port.stopListening()
        return defer.succeed(None)


class Registration(object):
    def __init__(self, ampManager, portstr, username):
        print "+++++++++ Registration.__init__"
        self.portstr = portstr
        "portstr this registration is active on"
        self.username = username
        "username of this registration"

        self.ampManager = ampManager

    def __repr__(self):
        return "<ampmanager.Registration for %s on %s>" % \
                            (self.username, self.portstr)

    def unregister(self):
        """
        Unregister this registration, removing the username from the port, and
        closing the port if there are no more users left.  Returns a Deferred.
        """
        print "+++++++++ Registration.unregister"
        return self.ampManager._unregister(self)

    def getPort(self):
        """
        Helper method for testing; returns the TCP port used for this
        registration, even if it was specified as 0 and thus allocated by the
        OS.
        """
        print "+++++++++ Registration.getPort"
        port = self.ampManager.ports[self.portstr]
        return port.getHost().port


class Master(DebugAMP, service.MultiService):
    def __init__(self, ampManager):
        service.MultiService.__init__(self)
        self.ampManager = ampManager
        self.callbacks_list = []

    def stopReceivingBoxes(self, reason):
        """ Called when slave disconnects """

        amp.AMP.stopReceivingBoxes(self, reason)
        if not self.ampManager.users.get(self.user):
            log.msg("That's weird, I can't find user '%s' that should be here!" % self.user)
            return
        if not hasattr(self, "persp"):
            _, pfactory = self.ampManager.users[self.user]
            d = defer.maybeDeferred(pfactory, self, self.user)
            def check(persp):
                if not persp:
                    raise ValueError("no perspective for '%s'" % user)
                return persp
            d.addCallback(check)
            def call_detached(persp):
                d = defer.maybeDeferred(persp.detached, self)
                d.addCallback(lambda _ : persp) # keep returning the perspective
                return d
            d.addCallback(call_detached)
        else:
            d = defer.maybeDeferred(self.persp.detached, self)
            d.addCallback(lambda persp : persp)

        if len(self.callbacks_list) > 0:
            d = defer.Deferred()
            for callback in self.callbacks_list:
                d.addCallback(callback)

        log.msg("Slave '%s' disconnected with reason '%s'" % (self.user, reason))

    def notifyOnDisconnect(self, callback):
        self.callbacks_list.append(callback)

    @RemoteAuth.responder
    def authSlave(self, user, password, features):
        if user in self.ampManager.users:
            passwd, _ = self.ampManager.users[user]
            if passwd != password:
                log.msg('invalid login from user \'%s\'' % user)
                # FIXME: Use "errors" field in Command subclasses to return an error
                error = [{'key': 'Error', 'value': 'Login or password incorrect'}]
                return {'features': error}
        else:
            log.msg('invalid login from unknown user \'%s\'' % user)
            # FIXME: Use "errors" field in Command subclasses to return an error
            error = [{'key': 'Error', 'value': 'Login or password incorrect'}]
            return {'features': error}
        log.msg('User \'%s\' authenticated!' % user)
        _, afactory = self.ampManager.users.get(user)
        d = defer.maybeDeferred(afactory, self, user)
        def check(persp):
            if not persp:
                raise ValueError("no perspective for '%s'" % user)
            return persp
        d.addCallback(check)
        def call_attached(persp):
            d = defer.maybeDeferred(persp.attached, self)
            d.addCallback(lambda _ : persp) # keep returning the perspective
            self.persp = persp
            return d
        d.addCallback(call_attached)
        self.user = user
        log.msg('Slave feature negotiation vector: %s' % pprint.pformat(features))
        features = [{'key': 'feature1', 'value': 'bar1'}, {'key': 'feature2', 'value': 'baz1'}]
        return {'features': features}

    @RemoteAcceptLog.responder
    def remoteAcceptLog(self, builder, logName, stream, data):
        log.msg('Slave builder: "%s", stream: "%s", log name: "%s", data:\n%  s'\
            % (builder, stream, logName, data)
        )
        return {}

    @RemoteUpdateSendRC.responder
    def remoteUpdateRC(self, builder, rc):
        log.msg('Slave builder: "%s" done command with rc: %d' % (builder, rc))
        return {}

    @Chunk.responder
    def receiveChunk(self, builder, chunk):
        builder_info = self.builders.get(builder)
        if builder_info is None:
            return {}
        writer = builder_info.get('writer')
        if writer is None:
            # file not exists
            writer = open(builder_info['file'], 'wb')
            builder_info['writer'] = writer
        writer.write(chunk)
        return {}

    @EndData.responder
    def closeWriter(self, builder):
        builder_info = self.builders.get(builder)
        if builder_info is None:
            return {}
        if builder_info.get('writer') is not None:
            builder_info['writer'].close()
            builder_info['writer'] = None
        builder_info['file'] = None
        return {}
