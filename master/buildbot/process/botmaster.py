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


from twisted.python import log
from twisted.python.failure import Failure
from twisted.internet import defer, reactor
from twisted.spread import pb
from twisted.application import service

from buildbot.util import eventual
from buildbot.process.builder import Builder
from buildbot import interfaces, locks
from buildbot.util.loop import DelegateLoop

class BotMaster(service.MultiService):

    """This is the master-side service which manages remote buildbot slaves.
    It provides them with BuildSlaves, and distributes file change
    notification messages to them.
    """

    debug = 0
    reactor = reactor

    def __init__(self, master):
        service.MultiService.__init__(self)
        self.master = master

        self.builders = {}
        self.builderNames = []
        # builders maps Builder names to instances of bb.p.builder.Builder,
        # which is the master-side object that defines and controls a build.
        # They are added by calling botmaster.addBuilder() from the startup
        # code.

        # self.slaves contains a ready BuildSlave instance for each
        # potential buildslave, i.e. all the ones listed in the config file.
        # If the slave is connected, self.slaves[slavename].slave will
        # contain a RemoteReference to their Bot instance. If it is not
        # connected, that attribute will hold None.
        self.slaves = {} # maps slavename to BuildSlave
        self.watchers = {}

        # self.locks holds the real Lock instances
        self.locks = {}

        # self.mergeRequests is the callable override for merging build
        # requests
        self.mergeRequests = None

        # self.prioritizeBuilders is the callable override for builder order
        # traversal
        self.prioritizeBuilders = None

        self.loop = DelegateLoop(self._get_processors)
        self.loop.setServiceParent(self)

        self.shuttingDown = False

        self.lastSlavePortnum = None

    def setMasterName(self, name, incarnation):
        self.master_name = name
        self.master_incarnation = incarnation

    def cleanShutdown(self):
        if self.shuttingDown:
            return
        log.msg("Initiating clean shutdown")
        self.shuttingDown = True

        # Wait for all builds to finish
        l = []
        for builder in self.builders.values():
            for build in builder.builder_status.getCurrentBuilds():
                l.append(build.waitUntilFinished())
        if len(l) == 0:
            log.msg("No running jobs, starting shutdown immediately")
            self.loop.trigger()
            d = self.loop.when_quiet()
        else:
            log.msg("Waiting for %i build(s) to finish" % len(l))
            d = defer.DeferredList(l)
            d.addCallback(lambda ign: self.loop.when_quiet())

        # Flush the eventual queue
        d.addCallback(eventual.flushEventualQueue)

        # Finally, shut the whole process down
        def shutdown(ign):
            # Double check that we're still supposed to be shutting down
            # The shutdown may have been cancelled!
            if self.shuttingDown:
                # Check that there really aren't any running builds
                for builder in self.builders.values():
                    n = len(builder.builder_status.getCurrentBuilds())
                    if n > 0:
                        log.msg("Not shutting down, builder %s has %i builds running" % (builder, n))
                        log.msg("Trying shutdown sequence again")
                        self.shuttingDown = False
                        self.cleanShutdown()
                        return
                log.msg("Stopping reactor")
                self.reactor.stop()
        d.addCallback(shutdown)
        return d

    def cancelCleanShutdown(self):
        if not self.shuttingDown:
            return
        log.msg("Cancelling clean shutdown")
        self.shuttingDown = False

    def _sortfunc(self, b1, b2):
        t1 = b1.getOldestRequestTime()
        t2 = b2.getOldestRequestTime()
        # If t1 or t2 is None, then there are no build requests,
        # so sort it at the end
        if t1 is None:
            return 1
        if t2 is None:
            return -1
        return cmp(t1, t2)

    def _sort_builders(self, parent, builders):
        return sorted(builders, self._sortfunc)

    def _get_processors(self):
        if self.shuttingDown:
            return []
        builders = self.builders.values()
        sorter = self.prioritizeBuilders or self._sort_builders
        try:
            builders = sorter(self.parent, builders)
        except:
            log.msg("Exception prioritizing builders")
            log.err(Failure())
            # leave them in the original order
        return [b.run for b in builders]

    def loadConfig_Slaves(self, new_slaves):
        new_portnum = (self.lastSlavePortnum is not None
                   and self.lastSlavePortnum != self.master.slavePortnum)
        if new_portnum:
            # it turns out this is pretty hard..
            raise ValueError("changing slavePortnum in reconfig is not supported")
        self.lastSlavePortnum = self.master.slavePortnum

        old_slaves = [c for c in list(self)
                      if interfaces.IBuildSlave.providedBy(c)]

        # identify added/removed slaves. For each slave we construct a tuple
        # of (name, password, class), and we consider the slave to be already
        # present if the tuples match. (we include the class to make sure
        # that BuildSlave(name,pw) is different than
        # SubclassOfBuildSlave(name,pw) ). If the password or class has
        # changed, we will remove the old version of the slave and replace it
        # with a new one. If anything else has changed, we just update the
        # old BuildSlave instance in place. If the name has changed, of
        # course, it looks exactly the same as deleting one slave and adding
        # an unrelated one.
        old_t = {}
        for s in old_slaves:
            old_t[(s.slavename, s.password, s.__class__)] = s
        new_t = {}
        for s in new_slaves:
            new_t[(s.slavename, s.password, s.__class__)] = s
        removed = [old_t[t]
                   for t in old_t
                   if t not in new_t]
        added = [new_t[t]
                 for t in new_t
                 if t not in old_t]
        remaining_t = [t
                       for t in new_t
                       if t in old_t]

        # removeSlave will hang up on the old bot
        dl = []
        for s in removed:
            dl.append(self.removeSlave(s))
        d = defer.DeferredList(dl, fireOnOneErrback=True)

        def add_new(res):
            for s in added:
                self.addSlave(s)
        d.addCallback(add_new)

        def update_remaining(_):
            for t in remaining_t:
                old_t[t].update(new_t[t])
        d.addCallback(update_remaining)

        return d

    def addSlave(self, s):
        s.setServiceParent(self)
        s.setBotmaster(self)
        self.slaves[s.slavename] = s
        s.pb_registration = self.master.pbmanager.register(
                self.master.slavePortnum, s.slavename,
                s.password, self.getPerspective)

    def removeSlave(self, s):
        d = s.disownServiceParent()
        d.addCallback(lambda _ : s.pb_registration.unregister())
        d.addCallback(lambda _ : self.slaves[s.slavename].disconnect())
        def delslave(_):
            del self.slaves[s.slavename]
        d.addCallback(delslave)
        return d

    def slaveLost(self, bot):
        for name, b in self.builders.items():
            if bot.slavename in b.slavenames:
                b.detached(bot)

    def getBuildersForSlave(self, slavename):
        return [b
                for b in self.builders.values()
                if slavename in b.slavenames]

    def getBuildernames(self):
        return self.builderNames

    def getBuilders(self):
        allBuilders = [self.builders[name] for name in self.builderNames]
        return allBuilders

    def setBuilders(self, builders):
        # TODO: remove self.builders and just use the Service hierarchy to
        # keep track of active builders. We could keep self.builderNames to
        # retain ordering, if it seems important.
        self.builders = {}
        self.builderNames = []
        d = defer.DeferredList([b.disownServiceParent() for b in list(self)
                                if isinstance(b, Builder)],
                               fireOnOneErrback=True)
        def _add(ign):
            log.msg("setBuilders._add: %s %s" % (list(self), builders))
            for b in builders:
                for slavename in b.slavenames:
                    # this is actually validated earlier
                    assert slavename in self.slaves
                self.builders[b.name] = b
                self.builderNames.append(b.name)
                b.setBotmaster(self)
                b.setServiceParent(self)
        d.addCallback(_add)
        d.addCallback(lambda ign: self._updateAllSlaves())
        return d

    def _updateAllSlaves(self):
        """Notify all buildslaves about changes in their Builders."""
        dl = []
        for s in self.slaves.values():
            d = s.updateSlave()
            d.addErrback(log.err)
            dl.append(d)
        return defer.DeferredList(dl)

    def shouldMergeRequests(self, builder, req1, req2):
        """Determine whether two BuildRequests should be merged for
        the given builder.

        """
        if self.mergeRequests is not None:
            if callable(self.mergeRequests):
                return self.mergeRequests(builder, req1, req2)
            elif self.mergeRequests == False:
                # To save typing, this allows c['mergeRequests'] = False
                return False
        return req1.canBeMergedWith(req2)

    def getPerspective(self, mind, slavename):
        sl = self.slaves[slavename]
        if not sl:
            return None

        # record when this connection attempt occurred
        sl.recordConnectTime()

        if sl.isConnected():
            # duplicate slave - send it to arbitration
            arb = DuplicateSlaveArbitrator(sl)
            return arb.getPerspective(mind, slavename)
        else:
            log.msg("slave '%s' attaching from %s" % (slavename, mind.broker.transport.getPeer()))
            return sl

    def stopService(self):
        for b in self.builders.values():
            b.builder_status.addPointEvent(["master", "shutdown"])
            b.builder_status.saveYourself()
        return service.MultiService.stopService(self)

    def getLockByID(self, lockid):
        """Convert a Lock identifier into an actual Lock instance.
        @param lockid: a locks.MasterLock or locks.SlaveLock instance
        @return: a locks.RealMasterLock or locks.RealSlaveLock instance
        """
        assert isinstance(lockid, (locks.MasterLock, locks.SlaveLock))
        if not lockid in self.locks:
            self.locks[lockid] = lockid.lockClass(lockid)
        # if the master.cfg file has changed maxCount= on the lock, the next
        # time a build is started, they'll get a new RealLock instance. Note
        # that this requires that MasterLock and SlaveLock (marker) instances
        # be hashable and that they should compare properly.
        return self.locks[lockid]

    def triggerNewBuildCheck(self):
        # TODO: old name -- should go
        self.loop.trigger()


class DuplicateSlaveArbitrator(object):
    """Utility class to arbitrate the situation when a new slave connects with
    the name of an existing, connected slave"""
    # There are several likely duplicate slave scenarios in practice:
    #
    # 1. two slaves are configured with the same username/password
    #
    # 2. the same slave process believes it is disconnected (due to a network
    # hiccup), and is trying to reconnect
    #
    # For the first case, we want to prevent the two slaves from repeatedly
    # superseding one another (which results in lots of failed builds), so we
    # will prefer the old slave.  However, for the second case we need to
    # detect situations where the old slave is "gone".  Sometimes "gone" means
    # that the TCP/IP connection to it is in a long timeout period (10-20m,
    # depending on the OS configuration), so this can take a while.

    PING_TIMEOUT = 10
    """Timeout for pinging the old slave.  Set this to something quite long, as
    a very busy slave (e.g., one sending a big log chunk) may take a while to
    return a ping.

    @ivar old_slave: L{buildbot.process.slavebuilder.AbstractSlaveBuilder}
    instance
    """

    def __init__(self, slave):
        self.old_slave = slave

    def getPerspective(self, mind, slavename):
        self.new_slave_mind = mind

        old_tport = self.old_slave.slave.broker.transport
        new_tport = mind.broker.transport
        log.msg("duplicate slave %s; delaying new slave (%s) and pinging old (%s)" % 
                (self.old_slave.slavename, new_tport.getPeer(), old_tport.getPeer()))

        # delay the new slave until we decide what to do with it
        self.new_slave_d = defer.Deferred()

        # Ping the old slave.  If this kills it, then we can allow the new
        # slave to connect.  If this does not kill it, then we disconnect
        # the new slave.
        self.ping_old_slave_done = False
        self.old_slave_connected = True
        self.ping_old_slave(new_tport.getPeer())

        # Print a message on the new slave, if possible.
        self.ping_new_slave_done = False
        self.ping_new_slave()

        return self.new_slave_d

    def ping_new_slave(self):
        d = self.new_slave_mind.callRemote("print",
            "master already has a connection named '%s' - checking its liveness"
                        % self.old_slave.slavename)
        def done(_):
            # failure or success, doesn't matter
            self.ping_new_slave_done = True
            self.maybe_done()
        d.addBoth(done)

    def ping_old_slave(self, new_peer):
        # set a timer on this ping, in case the network is bad.  TODO: a timeout
        # on the ping itself is not quite what we want.  If there is other data
        # flowing over the PB connection, then we should keep waiting.  Bug #1703
        def timeout():
            self.ping_old_slave_timeout = None
            self.ping_old_slave_timed_out = True
            self.old_slave_connected = False
            self.ping_old_slave_done = True
            self.maybe_done()
        self.ping_old_slave_timeout = reactor.callLater(self.PING_TIMEOUT, timeout)
        self.ping_old_slave_timed_out = False

        d = self.old_slave.slave.callRemote("print",
            "master got a duplicate connection from %s; keeping this one" % new_peer)

        def clear_timeout(r):
            if self.ping_old_slave_timeout:
                self.ping_old_slave_timeout.cancel()
                self.ping_old_slave_timeout = None
            return r
        d.addBoth(clear_timeout)

        def old_gone(f):
            if self.ping_old_slave_timed_out:
                return # ignore after timeout
            f.trap(pb.PBConnectionLost)
            log.msg(("connection lost while pinging old slave '%s' - " +
                     "keeping new slave") % self.old_slave.slavename)
            self.old_slave_connected = False
        d.addErrback(old_gone)

        def other_err(f):
            if self.ping_old_slave_timed_out:
                return # ignore after timeout
            log.msg("unexpected error while pinging old slave; disconnecting it")
            log.err(f)
            self.old_slave_connected = False
        d.addErrback(other_err)

        def done(_):
            if self.ping_old_slave_timed_out:
                return # ignore after timeout
            self.ping_old_slave_done = True
            self.maybe_done()
        d.addCallback(done)

    def maybe_done(self):
        if not self.ping_new_slave_done or not self.ping_old_slave_done:
            return

        # both pings are done, so sort out the results
        if self.old_slave_connected:
            self.disconnect_new_slave()
        else:
            self.start_new_slave()

    def start_new_slave(self, count=20):
        if not self.new_slave_d:
            return

        # we need to wait until the old slave has actually disconnected, which
        # can take a little while -- but don't wait forever!
        if self.old_slave.isConnected():
            if self.old_slave.slave:
                self.old_slave.slave.broker.transport.loseConnection()
            if count < 0:
                log.msg("WEIRD: want to start new slave, but the old slave will not disconnect")
                self.disconnect_new_slave()
            else:
                reactor.callLater(0.1, self.start_new_slave, count-1)
            return

        d = self.new_slave_d
        self.new_slave_d = None
        d.callback(self.old_slave)

    def disconnect_new_slave(self):
        if not self.new_slave_d:
            return
        d = self.new_slave_d
        self.new_slave_d = None
        log.msg("rejecting duplicate slave with exception")
        d.errback(Failure(RuntimeError("rejecting duplicate slave")))


