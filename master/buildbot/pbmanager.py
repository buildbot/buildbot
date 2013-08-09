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

from protocols import *

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
            log.msg("registering username '%s' on pb port %s: %s"
                % (username, portstr, pfactory))
        if username in self.users:
            raise KeyError, ("username '%s' is already registered on PB port %s"
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
        return "<pbmanager.Registration for %s on %s>" % \
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
#        Hello(self)
        log.msg('Slave feature negotiation vector: %s' % pprint.pformat(features))
        features = [{'key': 'feature1', 'value': 'bar1'}, {'key': 'feature2', 'value': 'baz1'}]
        return {'features': features}

    @RemoteAcceptLog.responder
    def remoteAcceptLog(self, builder, logName, stream, data):
        if hasattr(self, 'slave_authenticated') is False:
            log.msg('Log streaming rejected, because slavery didn\'t pass authentication')
            return {}
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


# class Dispatcher(service.Service):
#     implements(portal.IRealm, checkers.ICredentialsChecker)
#
#     credentialInterfaces = [ credentials.IUsernamePassword,
#                              credentials.IUsernameHashedPassword ]
#
#     def __init__(self, portstr):
#         print "+++++++++ Dispatcher.__init__"
#         self.portstr = portstr
#         self.users = {}
#
#         # there's lots of stuff to set up for a PB connection!
#         self.portal = portal.Portal(self)
#         self.portal.registerChecker(self)
#         self.serverFactory = pb.PBServerFactory(self.portal)
#         self.serverFactory.unsafeTracebacks = True
#         self.port = strports.listen(portstr, self.serverFactory)
#
#     def __repr__(self):
#         return "<pbmanager.Dispatcher for %s on %s>" % \
#                             (", ".join(self.users.keys()), self.portstr)
#
#     def stopService(self):
#         print "+++++++++ Dispatcher.stopService"
#         # stop listening on the port when shut down
#         d = defer.maybeDeferred(self.port.stopListening)
#         d.addCallback(lambda _ : service.Service.stopService(self))
#         return d
#
#     def register(self, username, password, pfactory):
#         print "+++++++++ Dispatcher.register"
#         if debug:
#             log.msg("registering username '%s' on pb port %s: %s"
#                 % (username, self.portstr, pfactory))
#         if username in self.users:
#             raise KeyError, ("username '%s' is already registered on PB port %s"
#                              % (username, self.portstr))
#         self.users[username] = (password, pfactory)
#
#     def unregister(self, username):
#         print "+++++++++ Dispatcher.unregister"
#         if debug:
#             log.msg("unregistering username '%s' on pb port %s"
#                     % (username, self.portstr))
#         del self.users[username]
#
#     # IRealm
#
#     def requestAvatar(self, username, mind, interface):
#         print "+++++++++ Dispatcher.reuqestAvatar"
#         assert interface == pb.IPerspective
#         if username not in self.users:
#             d = defer.succeed(None) # no perspective
#         else:
#             _, afactory = self.users.get(username)
#             d = defer.maybeDeferred(afactory, mind, username)
#
#         # check that we got a perspective
#         def check(persp):
#             if not persp:
#                 raise ValueError("no perspective for '%s'" % username)
#             return persp
#         d.addCallback(check)
#
#         # call the perspective's attached(mind)
#         def call_attached(persp):
#             d = defer.maybeDeferred(persp.attached, mind)
#             d.addCallback(lambda _ : persp) # keep returning the perspective
#             return d
#         d.addCallback(call_attached)
#
#         # return the tuple requestAvatar is expected to return
#         def done(persp):
#             return (pb.IPerspective, persp, lambda: persp.detached(mind))
#         d.addCallback(done)
#
#         return d
#     
#     # ICredentialsChecker
#
#     def requestAvatarId(self, creds):
#         print "+++++++++ Dispatcher.requestAvatarId"
#         if creds.username in self.users:
#             password, _ = self.users[creds.username]
#             d = defer.maybeDeferred(creds.checkPassword, password)
#             def check(matched):
#                 if not matched:
#                     log.msg("invalid login from user '%s'" % creds.username)
#                     return failure.Failure(error.UnauthorizedLogin())
#                 return creds.username
#             d.addCallback(check)
#             return d
#         else:
#             log.msg("invalid login from unknown user '%s'" % creds.username)
#             return defer.fail(error.UnauthorizedLogin())
