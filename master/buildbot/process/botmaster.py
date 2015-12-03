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
from future.utils import iteritems
from future.utils import itervalues

from buildbot import locks
from buildbot import util
from buildbot.process import metrics
from buildbot.process.builder import Builder
from buildbot.process.buildrequestdistributor import BuildRequestDistributor
from buildbot.util import service
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log


class BotMaster(service.ReconfigurableServiceMixin, service.AsyncMultiService):

    """This is the master-side service which manages remote buildbot slaves.
    It provides them with BuildSlaves, and distributes build requests to
    them."""

    debug = 0
    name = "botmaster"

    def __init__(self):
        service.AsyncMultiService.__init__(self)

        self.builders = {}
        self.builderNames = []
        # builders maps Builder names to instances of bb.p.builder.Builder,
        # which is the master-side object that defines and controls a build.

        self.watchers = {}

        # self.locks holds the real Lock instances
        self.locks = {}

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
        @d.addCallback
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

        # Finally, shut the whole process down
        @d.addCallback
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
        for name, b in iteritems(self.builders):
            if bot.slavename in b.config.slavenames:
                b.detached(bot)

    @metrics.countMethod('BotMaster.getBuildersForSlave()')
    def getBuildersForSlave(self, slavename):
        return [b for b in itervalues(self.builders)
                if slavename in b.config.slavenames]

    def getBuildernames(self):
        return self.builderNames

    def getBuilders(self):
        return list(itervalues(self.builders))

    @defer.inlineCallbacks
    def startService(self):
        @defer.inlineCallbacks
        def buildRequestAdded(key, msg):
            builderid = msg['builderid']
            buildername = None
            # convert builderid to buildername
            for builder in itervalues(self.builders):
                if builderid == (yield builder.getBuilderId()):
                    buildername = builder.name
                    break
            if buildername:
                self.maybeStartBuildsForBuilder(buildername)

        # consume both 'new' and 'unclaimed' build requests
        startConsuming = self.master.mq.startConsuming
        self.buildrequest_consumer_new = yield startConsuming(
            buildRequestAdded,
            ('buildrequests', None, "new"))
        self.buildrequest_consumer_unclaimed = yield startConsuming(
            buildRequestAdded,
            ('buildrequests', None, 'unclaimed'))
        yield service.AsyncMultiService.startService(self)

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config):
        timer = metrics.Timer("BotMaster.reconfigServiceWithBuildbotConfig")
        timer.start()

        # reconfigure builders
        yield self.reconfigServiceBuilders(new_config)

        # call up
        yield service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(self,
                                                                                   new_config)

        # try to start a build for every builder; this is necessary at master
        # startup, and a good idea in any other case
        self.maybeStartBuildsForAllBuilders()

        timer.stop()

    @defer.inlineCallbacks
    def reconfigServiceBuilders(self, new_config):

        timer = metrics.Timer("BotMaster.reconfigServiceBuilders")
        timer.start()

        # arrange builders by name
        old_by_name = dict([(b.name, b)
                            for b in list(self)
                            if isinstance(b, Builder)])
        old_set = set(old_by_name)
        new_by_name = dict([(bc.name, bc)
                            for bc in new_config.builders])
        new_set = set(new_by_name)

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

        self.builderNames = list(self.builders)

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
        for b in itervalues(self.builders):
            b.builder_status.addPointEvent(["master", "shutdown"])
            b.builder_status.saveYourself()
        return service.AsyncMultiService.stopService(self)

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
