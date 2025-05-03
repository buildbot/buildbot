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

import warnings
import weakref
from typing import TYPE_CHECKING
from typing import Any

from twisted.application import service
from twisted.internet import defer
from twisted.python import log

from buildbot import interfaces
from buildbot.data import resultspec
from buildbot.interfaces import IRenderable
from buildbot.process import buildrequest
from buildbot.process import workerforbuilder
from buildbot.process.build import Build
from buildbot.process.locks import get_real_locks_from_accesses_raw
from buildbot.process.properties import Properties
from buildbot.process.results import RETRY
from buildbot.util import bytes2unicode
from buildbot.util import epoch2datetime
from buildbot.util import service as util_service
from buildbot.util.render_description import render_description

if TYPE_CHECKING:
    from buildbot.config.builder import BuilderConfig
    from buildbot.config.master import MasterConfig
    from buildbot.data.workers import Worker
    from buildbot.master import BuildMaster


def enforceChosenWorker(bldr, workerforbuilder, breq):
    if 'workername' in breq.properties:
        workername = breq.properties['workername']
        if isinstance(workername, str):
            return workername == workerforbuilder.worker.workername

    return True


class Builder(util_service.ReconfigurableServiceMixin, service.MultiService):
    master: BuildMaster | None = None

    @property
    def expectations(self):
        warnings.warn("'Builder.expectations' is deprecated.", stacklevel=2)
        return None

    def __init__(self, name: str) -> None:
        super().__init__()
        self.name: str | None = name  # type: ignore[assignment]

        # this is filled on demand by getBuilderId; don't access it directly
        self._builderid = None

        # build/wannabuild slots: Build objects move along this sequence
        self.building: list[Build] = []
        # old_building holds active builds that were stolen from a predecessor
        self.old_building: weakref.WeakKeyDictionary[Build, Any] = weakref.WeakKeyDictionary()

        # workers which have connected but which are not yet available.
        # These are always in the ATTACHING state.
        self.attaching_workers: list[Worker] = []

        # workers at our disposal. Each WorkerForBuilder instance has a
        # .state that is IDLE, PINGING, or BUILDING. "PINGING" is used when a
        # Build is about to start, to make sure that they're still alive.
        self.workers: list[Worker] = []

        self.config: BuilderConfig | None = None

        # Updated in reconfigServiceWithBuildbotConfig
        self.project_name = None
        self.project_id = None

        # Tracks config version for locks
        self.config_version = None

    def _find_builder_config_by_name(self, new_config: MasterConfig) -> BuilderConfig | None:
        for builder_config in new_config.builders:
            if builder_config.name == self.name:
                return builder_config
        raise AssertionError(f"no config found for builder '{self.name}'")

    @defer.inlineCallbacks
    def find_project_id(self, project):
        if project is None:
            return project
        projectid = yield self.master.data.updates.find_project_id(project)
        if projectid is None:
            log.msg(f"{self} could not find project ID for project name {project}")
        return projectid

    @defer.inlineCallbacks
    def reconfigServiceWithBuildbotConfig(self, new_config):
        builder_config = self._find_builder_config_by_name(new_config)
        old_config = self.config
        self.config = builder_config
        self.config_version = self.master.config_version

        # allocate  builderid now, so that the builder is visible in the web
        # UI; without this, the builder wouldn't appear until it preformed a
        # build.
        builderid = yield self.getBuilderId()

        if self._has_updated_config_info(old_config, builder_config):
            projectid = yield self.find_project_id(builder_config.project)

            self.project_name = builder_config.project
            self.project_id = projectid

            yield self.master.data.updates.updateBuilderInfo(
                builderid,
                builder_config.description,
                builder_config.description_format,
                render_description(builder_config.description, builder_config.description_format),
                projectid,
                builder_config.tags,
            )

        # if we have any workers attached which are no longer configured,
        # drop them.
        new_workernames = set(builder_config.workernames)
        self.workers = [w for w in self.workers if w.worker.workername in new_workernames]

    def _has_updated_config_info(self, old_config, new_config):
        if old_config is None:
            return True
        if old_config.description != new_config.description:
            return True
        if old_config.description_format != new_config.description_format:
            return True
        if old_config.project != new_config.project:
            return True
        if old_config.tags != new_config.tags:
            return True
        return False

    def __repr__(self):
        return f"<Builder '{self.name!r}' at {id(self)}>"

    def getBuilderIdForName(self, name):
        # buildbot.config should ensure this is already unicode, but it doesn't
        # hurt to check again
        name = bytes2unicode(name)
        return self.master.data.updates.findBuilderId(name)

    @defer.inlineCallbacks
    def getBuilderId(self):
        # since findBuilderId is idempotent, there's no reason to add
        # additional locking around this function.
        if self._builderid:
            return self._builderid

        builderid = yield self.getBuilderIdForName(self.name)
        self._builderid = builderid
        return builderid

    @defer.inlineCallbacks
    def getOldestRequestTime(self):
        """Returns the submitted_at of the oldest unclaimed build request for
        this builder, or None if there are no build requests.

        @returns: datetime instance or None, via Deferred
        """
        bldrid = yield self.getBuilderId()
        unclaimed = yield self.master.data.get(
            ('builders', bldrid, 'buildrequests'),
            [resultspec.Filter('claimed', 'eq', [False])],
            order=['submitted_at'],
            limit=1,
        )
        if unclaimed:
            return unclaimed[0]['submitted_at']
        return None

    @defer.inlineCallbacks
    def getNewestCompleteTime(self):
        """Returns the complete_at of the latest completed build request for
        this builder, or None if there are no such build requests.

        @returns: datetime instance or None, via Deferred
        """
        bldrid = yield self.getBuilderId()
        completed = yield self.master.data.get(
            ('builders', bldrid, 'buildrequests'),
            [resultspec.Filter('complete', 'eq', [True])],
            order=['-complete_at'],
            limit=1,
        )
        if completed:
            return completed[0]['complete_at']
        else:
            return None

    @defer.inlineCallbacks
    def get_highest_priority(self):
        """Returns the priority of the highest priority unclaimed build request
        for this builder, or None if there are no build requests.

        @returns: priority or None, via Deferred
        """
        bldrid = yield self.getBuilderId()
        unclaimed = yield self.master.data.get(
            ('builders', bldrid, 'buildrequests'),
            [resultspec.Filter('claimed', 'eq', [False])],
            order=['-priority'],
            limit=1,
        )
        if unclaimed:
            return unclaimed[0]['priority']
        return None

    def getBuild(self, number):
        for b in self.building:
            if b.number == number:
                return b
        for b in self.old_building:
            if b.number == number:
                return b
        return None

    def addLatentWorker(self, worker):
        assert interfaces.ILatentWorker.providedBy(worker)
        for w in self.workers:
            if w == worker:
                break
        else:
            wfb = workerforbuilder.LatentWorkerForBuilder(worker, self)
            self.workers.append(wfb)
            self.botmaster.maybeStartBuildsForBuilder(self.name)

    @defer.inlineCallbacks
    def attached(self, worker, commands):
        """This is invoked by the Worker when the self.workername bot
        registers their builder.

        @type  worker: L{buildbot.worker.Worker}
        @param worker: the Worker that represents the worker as a whole
        @type  commands: dict: string -> string, or None
        @param commands: provides the worker's version of each RemoteCommand

        @rtype:  L{twisted.internet.defer.Deferred}
        @return: a Deferred that fires (with 'self') when the worker-side
                 builder is fully attached and ready to accept commands.
        """
        for w in self.attaching_workers + self.workers:
            if w.worker == worker:
                # already attached to them. This is fairly common, since
                # attached() gets called each time we receive the builder
                # list from the worker, and we ask for it each time we add or
                # remove a builder. So if the worker is hosting builders
                # A,B,C, and the config file changes A, we'll remove A and
                # re-add it, triggering two builder-list requests, getting
                # two redundant calls to attached() for B, and another two
                # for C.
                #
                # Therefore, when we see that we're already attached, we can
                # just ignore it.
                return self

        wfb = workerforbuilder.WorkerForBuilder(self)
        self.attaching_workers.append(wfb)

        try:
            yield wfb.attached(worker, commands)
            self.attaching_workers.remove(wfb)
            self.workers.append(wfb)
            return self

        except Exception as e:  # pragma: no cover
            # already log.err'ed by WorkerForBuilder._attachFailure
            # TODO: remove from self.workers (except that detached() should get
            #       run first, right?)
            log.err(e, 'worker failed to attach')
            return None

    def _find_wfb_by_worker(self, worker):
        for wfb in self.attaching_workers + self.workers:
            if wfb.worker == worker:
                return wfb
        return None

    def detached(self, worker):
        """This is called when the connection to the bot is lost."""
        wfb = self._find_wfb_by_worker(worker)
        if wfb is None:
            log.msg(
                f"WEIRD: Builder.detached({worker}) ({worker.workername})"
                f" not in attaching_workers({self.attaching_workers})"
                f" or workers({self.workers})"
            )
            return

        if wfb in self.attaching_workers:
            self.attaching_workers.remove(wfb)
        if wfb in self.workers:
            self.workers.remove(wfb)

        # inform the WorkerForBuilder that their worker went away
        wfb.detached()

    def getAvailableWorkers(self):
        return [wfb for wfb in self.workers if wfb.isAvailable()]

    @defer.inlineCallbacks
    def _setup_props_if_needed(self, props, workerforbuilder, buildrequest):
        # don't unnecessarily setup properties for build
        if props is not None:
            return props
        props = Properties()
        yield Build.setup_properties_known_before_build_starts(
            props, [buildrequest], self, workerforbuilder
        )
        return props

    @defer.inlineCallbacks
    def canStartBuild(self, workerforbuilder, buildrequest):
        can_start = True

        # check whether the locks that the build will acquire can actually be
        # acquired
        locks = self.config.locks
        worker = workerforbuilder.worker
        props = None

        if worker.builds_may_be_incompatible:
            # Check if the latent worker is actually compatible with the build.
            # The instance type of the worker may depend on the properties of
            # the build that substantiated it.
            props = yield self._setup_props_if_needed(props, workerforbuilder, buildrequest)
            can_start = yield worker.isCompatibleWithBuild(props)
            if not can_start:
                return False

        if IRenderable.providedBy(locks):
            # collect properties that would be set for a build if we
            # started it now and render locks using it
            props = yield self._setup_props_if_needed(props, workerforbuilder, buildrequest)
        else:
            props = None

        locks_to_acquire = yield get_real_locks_from_accesses_raw(
            locks, props, self, workerforbuilder, self.config_version
        )

        if locks_to_acquire:
            can_start = self._can_acquire_locks(locks_to_acquire)
            if not can_start:
                return False

        if callable(self.config.canStartBuild):
            can_start = yield self.config.canStartBuild(self, workerforbuilder, buildrequest)
        return can_start

    def _can_acquire_locks(self, lock_list):
        for lock, access in lock_list:
            if not lock.isAvailable(None, access):
                return False
        return True

    @defer.inlineCallbacks
    def _startBuildFor(self, workerforbuilder, buildrequests):
        build = self.config.factory.newBuild(buildrequests, self)

        props = build.getProperties()

        # give the properties a reference back to this build
        props.build = build

        yield Build.setup_properties_known_before_build_starts(
            props, build.requests, build.builder, workerforbuilder
        )

        log.msg(f"starting build {build} using worker {workerforbuilder}")

        build.setLocks(self.config.locks)

        if self.config.env:
            build.setWorkerEnvironment(self.config.env)

        # append the build to self.building
        self.building.append(build)

        # The worker is ready to go. workerforbuilder.buildStarted() sets its
        # state to BUILDING (so we won't try to use it for any other builds).
        # This gets set back to IDLE by the Build itself when it finishes.
        # Note: This can't be done in `Build.startBuild`, since it needs to be done
        # synchronously, before the BuildRequestDistributor looks at
        # another build request.
        workerforbuilder.buildStarted()

        # We put the result of startBuild into a fresh Deferred since _startBuildFor should not
        # wait until the build is finished.  This uses `maybeDeferred` to ensure that any exceptions
        # raised by startBuild are treated as deferred errbacks (see
        # http://trac.buildbot.net/ticket/2428).
        d = defer.maybeDeferred(build.startBuild, workerforbuilder)
        # this shouldn't happen. if it does, the worker will be wedged
        d.addErrback(
            log.err,
            'from a running build; this is a '
            'serious error - please file a bug at http://buildbot.net',
        )

        return True

    @defer.inlineCallbacks
    def setup_properties(self, props):
        builderid = yield self.getBuilderId()

        props.setProperty("buildername", self.name, "Builder")
        props.setProperty("builderid", builderid, "Builder")

        if self.project_name is not None:
            props.setProperty('projectname', self.project_name, 'Builder')
        if self.project_id is not None:
            props.setProperty('projectid', self.project_id, 'Builder')

        if self.config.properties:
            for propertyname in self.config.properties:
                props.setProperty(propertyname, self.config.properties[propertyname], "Builder")
        if self.config.defaultProperties:
            for propertyname in self.config.defaultProperties:
                if propertyname not in props:
                    props.setProperty(
                        propertyname, self.config.defaultProperties[propertyname], "Builder"
                    )

    def buildFinished(self, build, wfb):
        """This is called when the Build has finished (either success or
        failure). Any exceptions during the build are reported with
        results=FAILURE, not with an errback."""

        # by the time we get here, the Build has already released the worker,
        # which will trigger a check for any now-possible build requests
        # (maybeStartBuilds)

        results = build.results

        self.building.remove(build)
        if results == RETRY:
            d = self._resubmit_buildreqs(build)
            d.addErrback(log.err, 'while resubmitting a build request')
        else:
            complete_at_epoch = self.master.reactor.seconds()
            complete_at = epoch2datetime(complete_at_epoch)
            brids = [br.id for br in build.requests]

            d = self.master.data.updates.completeBuildRequests(
                brids, results, complete_at=complete_at
            )
            # nothing in particular to do with this deferred, so just log it if
            # it fails..
            d.addErrback(log.err, 'while marking build requests as completed')

        if wfb.worker:
            wfb.worker.releaseLocks()

    @defer.inlineCallbacks
    def _resubmit_buildreqs(self, build):
        brids = [br.id for br in build.requests]
        yield self.master.data.updates.unclaimBuildRequests(brids)

        # XXX method does not exist
        # self._msg_buildrequests_unclaimed(build.requests)

    # Build Creation

    def maybeStartBuild(self, workerforbuilder, breqs):
        # This method is called by the botmaster whenever this builder should
        # start a set of buildrequests on a worker. Do not call this method
        # directly - use master.botmaster.maybeStartBuildsForBuilder, or one of
        # the other similar methods if more appropriate

        # first, if we're not running, then don't start builds; stopService
        # uses this to ensure that any ongoing maybeStartBuild invocations
        # are complete before it stops.
        if not self.running:
            return defer.succeed(False)

        # If the build fails from here on out (e.g., because a worker has failed),
        # it will be handled outside of this function. TODO: test that!

        return self._startBuildFor(workerforbuilder, breqs)

    # a few utility functions to make the maybeStartBuild a bit shorter and
    # easier to read

    def getCollapseRequestsFn(self):
        """Helper function to determine which collapseRequests function to use
        from L{_collapseRequests}, or None for no merging"""
        # first, seek through builder, global, and the default
        collapseRequests_fn = self.config.collapseRequests
        if collapseRequests_fn is None:
            collapseRequests_fn = self.master.config.collapseRequests
        if collapseRequests_fn is None:
            collapseRequests_fn = True

        # then translate False and True properly
        if collapseRequests_fn is False:
            collapseRequests_fn = None
        elif collapseRequests_fn is True:
            collapseRequests_fn = self._defaultCollapseRequestFn

        return collapseRequests_fn

    @staticmethod
    def _defaultCollapseRequestFn(master, builder, brdict1, brdict2):
        return buildrequest.BuildRequest.canBeCollapsed(master, brdict1, brdict2)
