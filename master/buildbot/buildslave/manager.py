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

from buildbot import interfaces
from buildbot import util
from buildbot.buildslave.protocols import pb as bbpb
from buildbot.process import metrics
from buildbot.util import misc
from buildbot.util import service
from twisted.internet import defer
from twisted.python import log
from twisted.python import reflect
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
        self.pbReg = yield self.master.buildslaves.pb.updateRegistration(
            slave_config.slavename, slave_config.password,
            global_config.protocols['pb']['port'])

    def getPBPort(self):
        return self.pbReg.getPort()


class BuildslaveManager(service.ReconfigurableServiceMixin,
                        service.AsyncMultiService):

    name = "buildslaves"
    PING_TIMEOUT = 10
    reconfig_priority = 127

    def __init__(self, master):
        service.AsyncMultiService.__init__(self)
        self.setName('buildslaves')
        self.master = master

        self.pb = bbpb.Listener(self.master)
        self.pb.setServiceParent(self)

        # BuildslaveRegistration instances keyed by buildslave name
        self.registrations = {}

        # connection objects keyed by buildslave name
        self.connections = {}

        # self.slaves contains a ready BuildSlave instance for each
        # potential buildslave, i.e. all the ones listed in the config file.
        # If the slave is connected, self.slaves[slavename].slave will
        # contain a RemoteReference to their Bot instance. If it is not
        # connected, that attribute will hold None.
        self.slaves = {}  # maps slavename to BuildSlave

    @defer.inlineCallbacks
    def reconfigService(self, new_config):

        yield self.reconfigServiceSlaves(new_config)

        # reconfig any newly-added change sources, as well as existing
        yield service.ReconfigurableServiceMixin.reconfigService(self,
                                                                 new_config)

    @defer.inlineCallbacks
    def reconfigServiceSlaves(self, new_config):

        timer = metrics.Timer("BuildSlaveManager.reconfigServiceSlaves")
        timer.start()

        # arrange slaves by name
        old_by_name = dict([(s.slavename, s)
                            for s in list(self)
                            if interfaces.IBuildSlave.providedBy(s)])
        old_set = set(old_by_name.iterkeys())
        new_by_name = dict([(s.slavename, s)
                            for s in new_config.slaves])
        new_set = set(new_by_name.iterkeys())

        # calculate new slaves, by name, and removed slaves
        removed_names, added_names = util.diffSets(old_set, new_set)

        # find any slaves for which the fully qualified class name has
        # changed, and treat those as an add and remove
        for n in old_set & new_set:
            old = old_by_name[n]
            new = new_by_name[n]
            # detect changed class name
            if reflect.qual(old.__class__) != reflect.qual(new.__class__):
                removed_names.add(n)
                added_names.add(n)

        if removed_names or added_names:
            log.msg("adding %d new slaves, removing %d" %
                    (len(added_names), len(removed_names)))

            for n in removed_names:
                slave = old_by_name[n]

                del self.slaves[n]
                slave.master = None

                yield slave.disownServiceParent()

            for n in added_names:
                slave = new_by_name[n]
                yield slave.setServiceParent(self)
                self.slaves[n] = slave

        metrics.MetricCountEvent.log("num_slaves",
                                     len(self.slaves), absolute=True)

        timer.stop()

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
            except Exception, e:
                old_conn.loseConnection()
                log.msg("Got error while trying to ping connected slave %s:"
                        "%s" % (buildslaveName, e))
            log.msg("Old connection for '%s' was lost, accepting new" % buildslaveName)

        try:
            yield conn.remotePrint(message="attached")
            info = yield conn.remoteGetSlaveInfo()
            log.msg("Got slaveinfo from '%s'" % buildslaveName)
        except Exception, e:
            log.msg("Failed to communicate with slave '%s'\n"
                    "%s" % (buildslaveName, e)
                    )
            defer.returnValue(False)

        conn.info = info
        self.connections[buildslaveName] = conn

        def remove():
            del self.connections[buildslaveName]
        conn.notifyOnDisconnect(remove)

        # accept the connection
        defer.returnValue(True)
