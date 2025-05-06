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

from __future__ import annotations

from typing import TYPE_CHECKING

from twisted.internet import defer
from twisted.python import log

from buildbot import locks
from buildbot import util
from buildbot.db.buildrequests import AlreadyClaimedError
from buildbot.process import metrics
from buildbot.process.builder import Builder
from buildbot.process.buildrequestdistributor import BuildRequestDistributor
from buildbot.process.results import CANCELLED
from buildbot.process.results import RETRY
from buildbot.process.workerforbuilder import States
from buildbot.util import debounce
from buildbot.util import service
from buildbot.util.render_description import render_description
from buildbot.util.twisted import async_to_deferred
from buildbot.worker.latent import AbstractLatentWorker

if TYPE_CHECKING:
    from buildbot.worker import AbstractWorker


class LockRetrieverMixin:
    @defer.inlineCallbacks
    def getLockByID(self, lockid, config_version):
        """Convert a Lock identifier into an actual Lock instance.
        @lockid: a locks.MasterLock or locks.WorkerLock instance
        @config_version: The version of the config from which the list of locks has been
            acquired by the downstream user.
        @return: a locks.RealMasterLock or locks.RealWorkerLock instance

        The real locks are tracked using lock ID and config_version. The latter is used as a
        way to track most recent properties of real locks.

        This approach is needed because there's no central registry of lock access instances
        that are used within a Buildbot master.cfg (like there is for e.g c['builders']). All
        lock accesses bring all lock information with themselves as the lockid member.
        Therefore, the reconfig process is relatively complicated, because we don't know
        whether a specific access instance encodes lock information before reconfig or after.
        Taking into account config_version allows us to know when properties of a lock should
        be updated.

        Note that the user may create multiple lock ids with different maxCount values. It's
        unspecified which maxCount value the real lock will have.
        """
        assert isinstance(config_version, int)
        lock = yield lockid.lockClass.getService(self, lockid.name)

        if config_version > lock.config_version:
            lock.updateFromLockId(lockid, config_version)
        return lock

    def getLockFromLockAccess(self, access, config_version):
        # Convert a lock-access object into an actual Lock instance.
        if not isinstance(access, locks.LockAccess):
            # Buildbot 0.7.7 compatibility: user did not specify access
            access = access.defaultAccess()
        return self.getLockByID(access.lockid, config_version)

    @defer.inlineCallbacks
    def getLockFromLockAccesses(self, accesses, config_version):
        # converts locks to their real forms
        locks = yield defer.gatherResults(
            [self.getLockFromLockAccess(access, config_version) for access in accesses],
            consumeErrors=True,
        )
        return zip(locks, accesses)


class BotMaster(service.ReconfigurableServiceMixin, service.AsyncMultiService, LockRetrieverMixin):
    """This is the master-side service which manages remote buildbot workers.
    It provides them with Workers, and distributes build requests to
    them."""

    debug = 0
    name: str | None = "botmaster"  # type: ignore[assignment]

    def __init__(self) -> None:
        super().__init__()

        self.builders: dict[str, Builder] = {}
        self.builderNames: list[str] = []
        # builders maps Builder names to instances of bb.p.builder.Builder,
        # which is the master-side object that defines and controls a build.

        # Unused?
        self.watchers: dict[object, object] = {}

        self.shuttingDown = False

        # subscription to new build requests
        self.buildrequest_consumer_new = None
        self.buildrequest_consumer_unclaimed = None
        self.buildrequest_consumer_cancel = None

        # a distributor for incoming build requests; see below
        self.brd = BuildRequestDistributor(self)
        self.brd.setServiceParent(self)
        self._pending_builderids: set[str] = set()

        # Dictionary of build request ID to False or cancellation reason string in case cancellation
        # has been requested.
        self._starting_brid_to_cancel: dict[int, bool | str] = {}

    @defer.inlineCallbacks
    def cleanShutdown(self, quickMode=False, stopReactor=True):
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
        if quickMode:
            # if quick mode, builds will be cancelled, so stop scheduling altogether
            yield self.brd.disownServiceParent()
        else:
            # if not quick, still schedule waited child builds
            # other parent will never finish
            self.brd.distribute_only_waited_childs = True

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
                        is_building = (
                            build.workerforbuilder is not None
                            and build.workerforbuilder.state == States.BUILDING
                        )

                        # Master should not wait build.stopBuild for ages to complete if worker
                        # does not send any message about shutting the builds down quick enough.
                        # Just kill the connection with the worker
                        def lose_connection(b):
                            if b.workerforbuilder.worker.conn is not None:
                                b.workerforbuilder.worker.conn.loseConnection()

                        sheduled_call = self.master.reactor.callLater(5, lose_connection, build)

                        def cancel_lose_connection(_, call):
                            if call.active():
                                call.cancel()

                        d = build.stopBuild("Master Shutdown", results)
                        d.addBoth(cancel_lose_connection, sheduled_call)

                        if not is_building:
                            # if it is not building, then it must be a latent worker
                            # which is substantiating. Cancel it.
                            if build.workerforbuilder is not None and isinstance(
                                build.workerforbuilder.worker,
                                AbstractLatentWorker,
                            ):
                                build.workerforbuilder.worker.insubstantiate()
            # then wait for all builds to finish
            dl = []
            for builder in self.builders.values():
                for build in builder.building:
                    # build may be waiting for ping to worker to succeed which
                    # may never happen if the connection to worker was broken
                    # without TCP connection being severed
                    build.workerforbuilder.abortPingIfAny()

                    dl.append(build.waitUntilFinished())
            if not dl:
                log.msg("No running jobs, starting shutdown immediately")
            else:
                log.msg(f"Waiting for {len(dl)} build(s) to finish")
                yield defer.DeferredList(dl, consumeErrors=True)

            # Check that there really aren't any running builds
            n = 0
            for builder in self.builders.values():
                if builder.building:
                    num_builds = len(builder.building)
                    log.msg(f"Builder {builder} has {num_builds} builds running")
                    n += num_builds
            if n > 0:
                log.msg(f"Not shutting down, there are {n} builds running")
                log.msg("Trying shutdown sequence again")
                yield util.asyncSleep(1)
            else:
                break

        # shutdown was cancelled
        if not self.shuttingDown:
            if quickMode:
                yield self.brd.setServiceParent(self)
            else:
                self.brd.distribute_only_waited_childs = False

            return

        if stopReactor:
            log.msg("Stopping reactor")
            self.master.reactor.stop()

    def cancelCleanShutdown(self):
        """Cancel a clean shutdown that is already in progress, if any"""
        if not self.shuttingDown:
            return
        log.msg("Cancelling clean shutdown")
        self.shuttingDown = False

    @metrics.countMethod('BotMaster.workerLost()')
    def workerLost(self, bot: AbstractWorker):
        metrics.MetricCountEvent.log("BotMaster.attached_workers", -1)
        for b in self.builders.values():
            if b.config is not None and bot.workername in b.config.workernames:
                b.detached(bot)

    @metrics.countMethod('BotMaster.getBuildersForWorker()')
    def getBuildersForWorker(self, workername: str):
        return [
            b
            for b in self.builders.values()
            if b.config is not None and workername in b.config.workernames
        ]

    def getBuildernames(self):
        return self.builderNames

    def getBuilders(self):
        return list(self.builders.values())

    def _buildrequest_added(self, key, msg):
        self._pending_builderids.add(msg['builderid'])
        self._flush_pending_builders()

    # flush pending builders needs to be debounced, as per design the
    # buildrequests events will arrive in burst.
    # We debounce them to let the brd manage them as a whole
    # without having to debounce the brd itself
    @debounce.method(wait=0.1, until_idle=True)
    def _flush_pending_builders(self):
        if not self._pending_builderids:
            return
        buildernames = []
        for builderid in self._pending_builderids:
            builder = self.getBuilderById(builderid)
            if builder:
                buildernames.append(builder.name)
        self._pending_builderids.clear()
        self.brd.maybeStartBuildsOn(buildernames)

    def getBuilderById(self, builderid):
        return self._builders_byid.get(builderid)

    @defer.inlineCallbacks
    def startService(self):
        # consume both 'new' and 'unclaimed' build requests events
        startConsuming = self.master.mq.startConsuming
        self.buildrequest_consumer_new = yield startConsuming(
            self._buildrequest_added, ('buildrequests', None, "new")
        )
        self.buildrequest_consumer_unclaimed = yield startConsuming(
            self._buildrequest_added, ('buildrequests', None, 'unclaimed')
        )
        self.buildrequest_consumer_cancel = yield startConsuming(
            self._buildrequest_canceled, ('control', 'buildrequests', None, 'cancel')
        )
        yield super().startService()

    @defer.inlineCallbacks
    def _buildrequest_canceled(self, key, msg):
        brid = int(key[2])
        reason = msg.get('reason', 'no reason')

        # first, try to claim the request; if this fails, then it's too late to
        # cancel the build anyway
        try:
            b = yield self.master.db.buildrequests.claimBuildRequests(brids=[brid])
        except AlreadyClaimedError:
            self.maybe_cancel_in_progress_buildrequest(brid, reason)

            # In case the build request has been claimed on this master, the call to
            # maybe_cancel_in_progress_buildrequest above will ensure that they are either visible
            # to the data API call below, or canceled.
            builds = yield self.master.data.get(("buildrequests", brid, "builds"))

            # Any other master will observe the buildrequest cancel messages and will try to
            # cancel the buildrequest or builds internally.
            #
            # TODO: do not try to cancel builds that run on another master. Note that duplicate
            # cancels do not have any downside.
            for b in builds:
                self.master.mq.produce(
                    ("control", "builds", str(b['buildid']), "stop"), {'reason': reason}
                )
            return

        # then complete it with 'CANCELLED'; this is the closest we can get to
        # cancelling a request without running into trouble with dangling
        # references.
        yield self.master.data.updates.completeBuildRequests([brid], CANCELLED)
        brdict = yield self.master.db.buildrequests.getBuildRequest(brid)
        self.master.mq.produce(('buildrequests', str(brid), 'cancel'), brdict)

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config):
        timer = metrics.Timer("BotMaster.reconfigServiceWithBuildbotConfig")
        timer.start()

        yield self.reconfigProjects(new_config)
        yield self.reconfig_codebases(new_config)
        yield self.reconfigServiceBuilders(new_config)

        # call up
        yield super().reconfigServiceWithBuildbotConfig(new_config)

        # try to start a build for every builder; this is necessary at master
        # startup, and a good idea in any other case
        self.maybeStartBuildsForAllBuilders()

        timer.stop()

    @defer.inlineCallbacks
    def reconfigProjects(self, new_config):
        for project_config in new_config.projects:
            projectid = yield self.master.data.updates.find_project_id(project_config.name)
            yield self.master.data.updates.update_project_info(
                projectid,
                project_config.slug,
                project_config.description,
                project_config.description_format,
                render_description(project_config.description, project_config.description_format),
            )

    @async_to_deferred
    async def reconfig_codebases(self, new_config):
        for codebase_config in new_config.codebases:
            projectid = await self.master.data.updates.find_project_id(
                codebase_config.project, auto_create=False
            )
            if projectid is None:
                raise RuntimeError(
                    f'Could not find project {codebase_config.project} '
                    f'for codebase {codebase_config.name}'
                )

            codebaseid = await self.master.data.updates.find_codebase_id(
                projectid=projectid,
                name=codebase_config.name,
            )

            await self.master.data.updates.update_codebase_info(
                codebaseid=codebaseid,
                projectid=projectid,
                slug=codebase_config.slug,
            )

    @defer.inlineCallbacks
    def reconfigServiceBuilders(self, new_config):
        timer = metrics.Timer("BotMaster.reconfigServiceBuilders")
        timer.start()

        # arrange builders by name
        old_by_name = {b.name: b for b in list(self) if isinstance(b, Builder)}
        old_set = set(old_by_name)
        new_by_name = {bc.name: bc for bc in new_config.builders}
        new_set = set(new_by_name)

        # calculate new builders, by name, and removed builders
        removed_names, added_names = util.diffSets(old_set, new_set)

        if removed_names or added_names:
            log.msg(f"adding {len(added_names)} new builders, removing {len(removed_names)}")

            for n in removed_names:
                builder = old_by_name[n]

                del self.builders[n]
                builder.master = None
                builder.botmaster = None

                yield builder.disownServiceParent()

            for n in added_names:
                builder = Builder(n)
                self.builders[n] = builder

                builder.botmaster = self
                builder.master = self.master
                yield builder.setServiceParent(self)

        self.builderNames = list(self.builders)
        self._builders_byid = {}
        for builder in self.builders.values():
            self._builders_byid[(yield builder.getBuilderId())] = builder

        yield self.master.data.updates.updateBuilderList(
            self.master.masterid, [util.bytes2unicode(n) for n in self.builderNames]
        )

        metrics.MetricCountEvent.log("num_builders", len(self.builders), absolute=True)

        timer.stop()

    def stopService(self):
        if self.buildrequest_consumer_new:
            self.buildrequest_consumer_new.stopConsuming()
            self.buildrequest_consumer_new = None
        if self.buildrequest_consumer_unclaimed:
            self.buildrequest_consumer_unclaimed.stopConsuming()
            self.buildrequest_consumer_unclaimed = None
        if self.buildrequest_consumer_cancel:
            self.buildrequest_consumer_cancel.stopConsuming()
            self.buildrequest_consumer_cancel = None
        self._pending_builderids.clear()
        self._flush_pending_builders.stop()
        return super().stopService()

    # Used to track buildrequests that are in progress of being started on this master.
    def add_in_progress_buildrequest(self, brid):
        self._starting_brid_to_cancel[brid] = False

    def remove_in_progress_buildrequest(self, brid):
        return self._starting_brid_to_cancel.pop(brid, None)

    def maybe_cancel_in_progress_buildrequest(self, brid, reason):
        """
        Ensures that after this call any builds resulting from build request will be visible or
        cancelled.
        """
        if brid in self._starting_brid_to_cancel:
            self._starting_brid_to_cancel[brid] = reason

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
