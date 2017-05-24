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
from __future__ import print_function
from future.utils import iteritems
from future.utils import itervalues

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log

from buildbot import locks
from buildbot import util
from buildbot.process import metrics
from buildbot.process.builder import Builder
from buildbot.process.buildrequestdistributor import BuildRequestDistributor
from buildbot.process.results import CANCELLED
from buildbot.process.results import RETRY
from buildbot.process.workerforbuilder import States
from buildbot.util import service


class BotMaster(service.ReconfigurableServiceMixin, service.AsyncMultiService):

    """This is the master-side service which manages remote buildbot workers.
    It provides them with Workers, and distributes build requests to
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

        # subscription to new build requests
        self.buildrequest_consumer = None

        # a distributor for incoming build requests; see below
        self.brd = BuildRequestDistributor(self)
        self.brd.setServiceParent(self)

    @defer.inlineCallbacks
    def cleanShutdown(self, quickMode=False, stopReactor=True, _reactor=reactor):
        """Shut down the entire process, once all currently-running builds are
        complete.
        quickMode will mark all builds as retry (except the ones that were triggered)
        """
        if self.shuttingDown:
            return
        log.msg("Initiating clean shutdown")
        self.shuttingDown = True
        # first, stop the distributor; this will finish any ongoing scheduling
        # operations before firing
        yield self.brd.disownServiceParent()

        # Double check that we're still supposed to be shutting down
        # The shutdown may have been cancelled!
        while self.shuttingDown:
            if quickMode:
                for builder in self.builders.values():
                    # As we stop the builds, builder.building might change during loop
                    # so we need to copy the list
                    for build in list(builder.building):
                        # if build is waited for then this is a sub-build, so
                        # no need to retry it
                        if sum(br.waitedFor for br in build.requests):
                            results = CANCELLED
                        else:
                            results = RETRY
                        is_building = build.workerforbuilder.state == States.BUILDING
                        build.stopBuild("Master Shutdown", results)
                        if not is_building:
                            # if it is not building, then it must be a latent worker
                            # which is substantiating. Cancel it.
                            build.workerforbuilder.worker.insubstantiate()
            # then wait for all builds to finish
            dl = []
            for builder in self.builders.values():
                for build in builder.building:
                    dl.append(build.waitUntilFinished())
            if not dl:
                log.msg("No running jobs, starting shutdown immediately")
            else:
                log.msg("Waiting for %i build(s) to finish" % len(dl))
                yield defer.DeferredList(dl)

            # Check that there really aren't any running builds
            n = 0
            for builder in self.builders.values():
                if builder.building:
                    num_builds = len(builder.building)
                    log.msg("Builder %s has %i builds running" %
                            (builder, num_builds))
                    n += num_builds
            if n > 0:
                log.msg(
                    "Not shutting down, there are %i builds running" % n)
                log.msg("Trying shutdown sequence again")
                yield util.asyncSleep(1)
            else:
                if stopReactor and self.shuttingDown:
                    log.msg("Stopping reactor")
                    _reactor.stop()
                break

        if not self.shuttingDown:
            yield self.brd.setServiceParent(self)

    def cancelCleanShutdown(self):
        """Cancel a clean shutdown that is already in progress, if any"""
        if not self.shuttingDown:
            return
        log.msg("Cancelling clean shutdown")
        self.shuttingDown = False

    @metrics.countMethod('BotMaster.workerLost()')
    def workerLost(self, bot):
        metrics.MetricCountEvent.log("BotMaster.attached_workers", -1)
        for name, b in iteritems(self.builders):
            if bot.workername in b.config.workernames:
                b.detached(bot)

    @metrics.countMethod('BotMaster.getBuildersForWorker()')
    def getBuildersForWorker(self, workername):
        return [b for b in itervalues(self.builders)
                if workername in b.config.workernames]

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

                # pylint: disable=cell-var-from-loop
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
        return service.AsyncMultiService.stopService(self)

    def getLockByID(self, lockid):
        """Convert a Lock identifier into an actual Lock instance.
        @param lockid: a locks.MasterLock or locks.WorkerLock instance
        @return: a locks.RealMasterLock or locks.RealWorkerLock instance
        """
        assert isinstance(lockid, (locks.MasterLock, locks.WorkerLock))
        if lockid not in self.locks:
            self.locks[lockid] = lockid.lockClass(lockid)
        # if the master.cfg file has changed maxCount= on the lock, the next
        # time a build is started, they'll get a new RealLock instance. Note
        # that this requires that MasterLock and WorkerLock (marker) instances
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

    def maybeStartBuildsForWorker(self, worker_name):
        """
        Call this when something suggests that a particular worker may now be
        available to start a build.

        @param worker_name: the name of the worker
        """
        builders = self.getBuildersForWorker(worker_name)
        self.brd.maybeStartBuildsOn([b.name for b in builders])

    def maybeStartBuildsForAllBuilders(self):
        """
        Call this when something suggests that this would be a good time to
        start some builds, but nothing more specific.
        """
        self.brd.maybeStartBuildsOn(self.builderNames)
