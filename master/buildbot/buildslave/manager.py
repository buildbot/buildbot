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

from buildbot.buildslave.protocols import pb as bbpb
from buildbot.process.measured_service import MeasuredBuildbotServiceManager
from buildbot.util import misc
from buildbot.util import service
from twisted.internet import defer
from twisted.python import log
from twisted.python.failure import Failure


class BuildslaveRegistration(object):

    __slots__ = ['master', 'buildslave', 'pbReg']

    def __init__(self, master, buildslave):
        self.master = master
        self.buildslave = buildslave

    def __repr__(self):
        return "<%s for %r>" % (self.__class__.__name__, self.buildslave.slavename)

    @defer.inlineCallbacks
    def unregister(self):
        bs = self.buildslave
        # update with portStr=None to remove any registration in place
        yield self.master.buildslaves.pb.updateRegistration(
            bs.slavename, bs.password, None)
        yield self.master.buildslaves._unregister(self)

    @defer.inlineCallbacks
    def update(self, slave_config, global_config):
        # For most protocols, there's nothing to do, but for PB we must
        # update the registration in case the port or password has changed.
        if 'pb' in global_config.protocols:
            self.pbReg = yield self.master.buildslaves.pb.updateRegistration(
                slave_config.slavename, slave_config.password,
                global_config.protocols['pb']['port'])

    def getPBPort(self):
        return self.pbReg.getPort()


class BuildslaveManager(MeasuredBuildbotServiceManager):

    name = "BuildslaveManager"
    managed_services_name = "buildslaves"

    config_attr = "slaves"
    PING_TIMEOUT = 10
    reconfig_priority = 127

    def __init__(self, master):
        service.AsyncMultiService.__init__(self)

        self.pb = bbpb.Listener()
        self.pb.setServiceParent(master)

        # BuildslaveRegistration instances keyed by buildslave name
        self.registrations = {}

        # connection objects keyed by buildslave name
        self.connections = {}

    @property
    def slaves(self):
        # self.slaves contains a ready BuildSlave instance for each
        # potential buildslave, i.e. all the ones listed in the config file.
        # If the slave is connected, self.slaves[slavename].slave will
        # contain a RemoteReference to their Bot instance. If it is not
        # connected, that attribute will hold None.
        # slaves attribute is actually just an alias to multiService's namedService
        return self.namedServices

    def getBuildslaveByName(self, buildslaveName):
        return self.registrations[buildslaveName].buildslave

    def register(self, buildslave):
        # TODO: doc that reg.update must be called, too
        buildslaveName = buildslave.slavename
        reg = BuildslaveRegistration(self.master, buildslave)
        self.registrations[buildslaveName] = reg
        return defer.succeed(reg)

    def _unregister(self, registration):
        del self.registrations[registration.buildslave.slavename]

    @defer.inlineCallbacks
    def newConnection(self, conn, buildslaveName):
        if buildslaveName in self.connections:
            log.msg("Got duplication connection from '%s'"
                    " starting arbitration procedure" % buildslaveName)
            old_conn = self.connections[buildslaveName]
            try:
                yield misc.cancelAfter(self.PING_TIMEOUT,
                                       old_conn.remotePrint("master got a duplicate connection"))
                # if we get here then old connection is still alive, and new
                # should be rejected
                defer.returnValue(
                    Failure(RuntimeError("rejecting duplicate slave"))
                )
            except defer.CancelledError:
                old_conn.loseConnection()
                log.msg("Connected slave '%s' ping timed out after %d seconds"
                        % (buildslaveName, self.PING_TIMEOUT))
            except Exception as e:
                old_conn.loseConnection()
                log.msg("Got error while trying to ping connected slave %s:"
                        "%s" % (buildslaveName, e))
            log.msg("Old connection for '%s' was lost, accepting new" % buildslaveName)

        try:
            yield conn.remotePrint(message="attached")
            info = yield conn.remoteGetSlaveInfo()
            log.msg("Got slaveinfo from '%s'" % buildslaveName)
        except Exception as e:
            log.msg("Failed to communicate with slave '%s'\n"
                    "%s" % (buildslaveName, e))
            defer.returnValue(False)

        conn.info = info
        self.connections[buildslaveName] = conn

        def remove():
            del self.connections[buildslaveName]
        conn.notifyOnDisconnect(remove)

        # accept the connection
        defer.returnValue(True)
