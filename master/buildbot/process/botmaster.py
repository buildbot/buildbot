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


from buildbot import config
from buildbot import interfaces
from buildbot import locks
from buildbot import util
from buildbot.process import metrics
from buildbot.process.builder import Builder
from buildbot.process.buildrequestdistributor import BuildRequestDistributor
from buildbot.util import service
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.python import reflect


class BotMaster(config.ReconfigurableServiceMixin, service.AsyncMultiService):

    """This is the master-side service which manages remote buildbot slaves.
    It provides them with BuildSlaves, and distributes build requests to
    them."""

    debug = 0

    def __init__(self, master):
        service.AsyncMultiService.__init__(self)
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
        self.buildrequest_consumer = None

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
        def buildRequestAdded(key, msg):
            self.maybeStartBuildsForBuilder(msg['buildername'])
        # consume both 'new' and 'unclaimed' build requests

        # TODO: Support for BuildRequest doesn't exist yet
        # It's a temporary fix in order to wake up the BuildRequestDistributor
        #
        # self.buildrequest_consumer_new = self.master.mq.startConsuming(
        #     buildRequestAdded,
        #     ('buildrequest', None, None, None, 'new'))
        self.buildrequest_consumer_new = self.master.mq.startConsuming(
            buildRequestAdded,
            ('buildset', None, 'builder', None, 'buildrequest', None, 'new'))
        self.buildrequest_consumer_unclaimed = self.master.mq.startConsuming(
            buildRequestAdded,
            ('buildrequest', None, None, None, 'unclaimed'))
        return service.AsyncMultiService.startService(self)

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

                yield slave.disownServiceParent()

            for n in added_names:
                slave = new_by_name[n]
                yield slave.setServiceParent(self)
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
                yield builder.setServiceParent(self)

        self.builderNames = self.builders.keys()

        yield self.master.data.updates.updateBuilderList(
            self.master.masterid,
            [util.ascii2unicode(n) for n in self.builderNames])

        metrics.MetricCountEvent.log("num_builders",
                                     len(self.builders), absolute=True)

        timer.stop()

    def stopService(self):
        if self.buildrequest_consumer_new:
            self.buildrequest_consumer_new.stopConsuming()
            self.buildrequest_consumer_new = None
        if self.buildrequest_consumer_unclaimed:
            self.buildrequest_consumer_unclaimed.stopConsuming()
            self.buildrequest_consumer_unclaimed = None
        for b in self.builders.values():
            b.builder_status.addPointEvent(["master", "shutdown"])
            b.builder_status.saveYourself()
        return service.AsyncMultiService.stopService(self)

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

    def maybeStartBuildsForSlave(self, buildslave_name):
        """
        Call this when something suggests that a particular slave may now be
        available to start a build.

        @param buildslave_name: the name of the slave
        """
        builders = self.getBuildersForSlave(buildslave_name)
        self.brd.maybeStartBuildsOn([b.name for b in builders])

    def maybeStartBuildsForAllBuilders(self):
        """
        Call this when something suggests that this would be a good time to
        start some builds, but nothing more specific.
        """
        self.brd.maybeStartBuildsOn(self.builderNames)
