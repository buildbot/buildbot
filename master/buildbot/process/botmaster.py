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


from twisted.application import service
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.python import reflect
from twisted.python.failure import Failure
from twisted.spread import pb

from buildbot import config
from buildbot import interfaces
from buildbot import locks
from buildbot import util
from buildbot.process import metrics
from buildbot.process.builder import Builder
from buildbot.process.buildrequestdistributor import BuildRequestDistributor


class BotMaster(config.ReconfigurableServiceMixin, service.MultiService):

    """This is the master-side service which manages remote buildbot slaves.
    It provides them with BuildSlaves, and distributes build requests to
    them."""

    debug = 0

    def __init__(self, master):
        service.MultiService.__init__(self)
        self.setName("botmaster")
        self.master = master

        self.builders = {}
        self.builderNames = []
        # builders maps Builder names to instances of bb.p.builder.Builder,
        # which is the master-side object that defines and controls a build.

        # self.slaves contains a ready BuildSlave instance for each
        # potential buildslave, i.e. all the ones listed in the config file.
        # If the slave is connected, self.slaves[slavename].slave will
        # contain a RemoteReference to their Bot instance. If it is not
        # connected, that attribute will hold None.
        self.slaves = {}  # maps slavename to BuildSlave
        self.watchers = {}

        # self.locks holds the real Lock instances
        self.locks = {}

        # self.mergeRequests is the callable override for merging build
        # requests
        self.mergeRequests = None

        self.shuttingDown = False

        self.lastSlavePortnum = None

        # subscription to new build requests
        self.buildrequest_sub = None

        # a distributor for incoming build requests; see below
        self.brd = BuildRequestDistributor(self)
        self.brd.setServiceParent(self)

    def cleanShutdown(self, _reactor=reactor):
        """Shut down the entire process, once all currently-running builds are
        complete."""
        if self.shuttingDown:
            return
        log.msg("Initiating clean shutdown")
        self.shuttingDown = True

        # first, stop the distributor; this will finish any ongoing scheduling
        # operations before firing
        d = self.brd.stopService()

        # then wait for all builds to finish
        def wait(_):
            l = []
            for builder in self.builders.values():
                for build in builder.builder_status.getCurrentBuilds():
                    l.append(build.waitUntilFinished())
            if len(l) == 0:
                log.msg("No running jobs, starting shutdown immediately")
            else:
                log.msg("Waiting for %i build(s) to finish" % len(l))
                return defer.DeferredList(l)
        d.addCallback(wait)

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
                _reactor.stop()
            else:
                self.brd.startService()
        d.addCallback(shutdown)
        d.addErrback(log.err, 'while processing cleanShutdown')

    def cancelCleanShutdown(self):
        """Cancel a clean shutdown that is already in progress, if any"""
        if not self.shuttingDown:
            return
        log.msg("Cancelling clean shutdown")
        self.shuttingDown = False

    @metrics.countMethod('BotMaster.slaveLost()')
    def slaveLost(self, bot):
        metrics.MetricCountEvent.log("BotMaster.attached_slaves", -1)
        for name, b in self.builders.items():
            if bot.slavename in b.config.slavenames:
                b.detached(bot)

    @metrics.countMethod('BotMaster.getBuildersForSlave()')
    def getBuildersForSlave(self, slavename):
        return [b for b in self.builders.values()
                if slavename in b.config.slavenames]

    def getBuildernames(self):
        return self.builderNames

    def getBuilders(self):
        return self.builders.values()

    def startService(self):
        def buildRequestAdded(notif):
            self.maybeStartBuildsForBuilder(notif['buildername'])
        self.buildrequest_sub = \
            self.master.subscribeToBuildRequests(buildRequestAdded)
        service.MultiService.startService(self)

    @defer.inlineCallbacks
    def reconfigService(self, new_config):
        timer = metrics.Timer("BotMaster.reconfigService")
        timer.start()

        # reconfigure slaves
        yield self.reconfigServiceSlaves(new_config)

        # reconfigure builders
        yield self.reconfigServiceBuilders(new_config)

        # call up
        yield config.ReconfigurableServiceMixin.reconfigService(self,
                                                                new_config)

        # try to start a build for every builder; this is necessary at master
        # startup, and a good idea in any other case
        self.maybeStartBuildsForAllBuilders()

        timer.stop()

    @defer.inlineCallbacks
    def reconfigServiceSlaves(self, new_config):

        timer = metrics.Timer("BotMaster.reconfigServiceSlaves")
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
                slave.botmaster = None

                yield defer.maybeDeferred(lambda:
                                          slave.disownServiceParent())

            for n in added_names:
                slave = new_by_name[n]
                slave.setServiceParent(self)
                self.slaves[n] = slave

        metrics.MetricCountEvent.log("num_slaves",
                                     len(self.slaves), absolute=True)

        timer.stop()

    @defer.inlineCallbacks
    def reconfigServiceBuilders(self, new_config):

        timer = metrics.Timer("BotMaster.reconfigServiceBuilders")
        timer.start()

        # arrange builders by name
        old_by_name = dict([(b.name, b)
                            for b in list(self)
                            if isinstance(b, Builder)])
        old_set = set(old_by_name.iterkeys())
        new_by_name = dict([(bc.name, bc)
                            for bc in new_config.builders])
        new_set = set(new_by_name.iterkeys())

        # calculate new builders, by name, and removed builders
        removed_names, added_names = util.diffSets(old_set, new_set)

        if removed_names or added_names:
            log.msg("adding %d new builders, removing %d" %
                    (len(added_names), len(removed_names)))

            for n in removed_names:
                builder = old_by_name[n]

                del self.builders[n]
                builder.master = None
                builder.botmaster = None

                yield defer.maybeDeferred(lambda:
                                          builder.disownServiceParent())

            for n in added_names:
                builder = Builder(n)
                self.builders[n] = builder

                builder.botmaster = self
                builder.master = self.master
                builder.setServiceParent(self)

        self.builderNames = self.builders.keys()

        metrics.MetricCountEvent.log("num_builders",
                                     len(self.builders), absolute=True)

        timer.stop()

    def stopService(self):
        if self.buildrequest_sub:
            self.buildrequest_sub.unsubscribe()
            self.buildrequest_sub = None
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
        if lockid not in self.locks:
            self.locks[lockid] = lockid.lockClass(lockid)
        # if the master.cfg file has changed maxCount= on the lock, the next
        # time a build is started, they'll get a new RealLock instance. Note
        # that this requires that MasterLock and SlaveLock (marker) instances
        # be hashable and that they should compare properly.
        return self.locks[lockid]

    def getLockFromLockAccess(self, access):
        # Convert a lock-access object into an actual Lock instance.
        if not isinstance(access, locks.LockAccess):
            # Buildbot 0.7.7 compability: user did not specify access
            access = access.defaultAccess()
        lock = self.getLockByID(access.lockid)
        return lock

    def maybeStartBuildsForBuilder(self, buildername):
        """
        Call this when something suggests that a particular builder may now
        be available to start a build.

        @param buildername: the name of the builder
        """
        self.brd.maybeStartBuildsOn([buildername])

    def maybeStartBuildsForSlave(self, slave_name):
        """
        Call this when something suggests that a particular slave may now be
        available to start a build.

        @param slave_name: the name of the slave
        """
        builders = self.getBuildersForSlave(slave_name)
        self.brd.maybeStartBuildsOn([b.name for b in builders])

    def maybeStartBuildsForAllBuilders(self):
        """
        Call this when something suggests that this would be a good time to
        start some builds, but nothing more specific.
        """
        self.brd.maybeStartBuildsOn(self.builderNames)


class DuplicateSlaveArbitrator(object):

    """Utility class to arbitrate the situation when a new slave connects with
    the name of an existing, connected slave

    @ivar buildslave: L{buildbot.process.slavebuilder.AbstractBuildSlave}
    instance
    @ivar old_remote: L{RemoteReference} to the old slave
    @ivar new_remote: L{RemoteReference} to the new slave
    """
    _reactor = reactor  # for testing

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
    """

    def __init__(self, buildslave):
        self.buildslave = buildslave
        self.old_remote = self.buildslave.slave

    def getPerspective(self, mind, slavename):
        self.new_remote = mind
        self.ping_old_slave_done = False
        self.old_slave_connected = True
        self.ping_new_slave_done = False

        old_tport = self.old_remote.broker.transport
        new_tport = self.new_remote.broker.transport
        log.msg("duplicate slave %s; delaying new slave (%s) and pinging old "
                "(%s)" % (self.buildslave.slavename, new_tport.getPeer(),
                          old_tport.getPeer()))

        # delay the new slave until we decide what to do with it
        d = self.new_slave_d = defer.Deferred()

        # Ping the old slave.  If this kills it, then we can allow the new
        # slave to connect.  If this does not kill it, then we disconnect
        # the new slave.
        self.ping_old_slave(new_tport.getPeer())

        # Print a message on the new slave, if possible.
        self.ping_new_slave()

        return d

    def ping_new_slave(self):
        d = defer.maybeDeferred(lambda:
                                self.new_remote.callRemote("print", "master already has a "
                                                           "connection named '%s' - checking its liveness"
                                                           % self.buildslave.slavename))

        def done(_):
            # failure or success, doesn't matter - the ping is done.
            self.ping_new_slave_done = True
            self.maybe_done()
        d.addBoth(done)

    def ping_old_slave(self, new_peer):
        # set a timer on this ping, in case the network is bad.  TODO: a
        # timeout on the ping itself is not quite what we want.  If there is
        # other data flowing over the PB connection, then we should keep
        # waiting.  Bug #1703
        def timeout():
            self.ping_old_slave_timeout = None
            self.ping_old_slave_timed_out = True
            self.old_slave_connected = False
            self.ping_old_slave_done = True
            self.maybe_done()
        self.ping_old_slave_timeout = self._reactor.callLater(
            self.PING_TIMEOUT, timeout)
        self.ping_old_slave_timed_out = False

        # call this in maybeDeferred because callRemote tends to raise
        # exceptions instead of returning Failures
        d = defer.maybeDeferred(lambda:
                                self.old_remote.callRemote("print",
                                                           "master got a duplicate connection from %s; keeping this one"
                                                           % new_peer))

        def clear_timeout(r):
            if self.ping_old_slave_timeout:
                self.ping_old_slave_timeout.cancel()
                self.ping_old_slave_timeout = None
            return r
        d.addBoth(clear_timeout)

        def old_gone(f):
            if self.ping_old_slave_timed_out:
                return  # ignore after timeout
            f.trap(pb.PBConnectionLost, pb.DeadReferenceError)
            log.msg(("connection lost while pinging old slave '%s' - " +
                     "keeping new slave") % self.buildslave.slavename)
            self.old_slave_connected = False
        d.addErrback(old_gone)

        def other_err(f):
            log.err(f, "unexpected error pinging old slave; disconnecting it")
            self.old_slave_connected = False
        d.addErrback(other_err)

        def done(_):
            if self.ping_old_slave_timed_out:
                return  # ignore after timeout
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

    def start_new_slave(self):
        # just in case
        if not self.new_slave_d:  # pragma: ignore
            return

        d = self.new_slave_d
        self.new_slave_d = None

        if self.buildslave.isConnected():
            # we need to wait until the old slave has fully detached, which can
            # take a little while as buffers drain, etc.
            def detached():
                d.callback(self.buildslave)
            self.buildslave.subscribeToDetach(detached)
            self.old_remote.broker.transport.loseConnection()
        else:  # pragma: ignore
            # by some unusual timing, it's quite possible that the old slave
            # has disconnected while the arbitration was going on.  In that
            # case, we're already done!
            d.callback(self.buildslave)

    def disconnect_new_slave(self):
        # just in case
        if not self.new_slave_d:  # pragma: ignore
            return

        d = self.new_slave_d
        self.new_slave_d = None
        log.msg("rejecting duplicate slave with exception")
        d.errback(Failure(RuntimeError("rejecting duplicate slave")))
