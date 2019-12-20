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


from functools import reduce

from twisted.internet import defer
from twisted.internet import error
from twisted.python import components
from twisted.python import failure
from twisted.python import log
from twisted.python.failure import Failure
from zope.interface import implementer

from buildbot import interfaces
from buildbot.process import buildstep
from buildbot.process import metrics
from buildbot.process import properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.process.results import computeResultAndTermination
from buildbot.process.results import statusToString
from buildbot.process.results import worst_status
from buildbot.reporters.utils import getURLForBuild
from buildbot.util import bytes2unicode
from buildbot.util.eventual import eventually


@implementer(interfaces.IBuildControl)
class Build(properties.PropertiesMixin):

    """I represent a single build by a single worker. Specialized Builders can
    use subclasses of Build to hold status information unique to those build
    processes.

    I control B{how} the build proceeds. The actual build is broken up into a
    series of steps, saved in the .buildSteps[] array as a list of
    L{buildbot.process.step.BuildStep} objects. Each step is a single remote
    command, possibly a shell command.

    During the build, I put status information into my C{BuildStatus}
    gatherer.

    After the build, I go away.

    I can be used by a factory by setting buildClass on
    L{buildbot.process.factory.BuildFactory}

    @ivar requests: the list of L{BuildRequest}s that triggered me
    @ivar build_status: the L{buildbot.status.build.BuildStatus} that
                        collects our status
    """

    VIRTUAL_BUILDERNAME_PROP = "virtual_builder_name"
    VIRTUAL_BUILDERDESCRIPTION_PROP = "virtual_builder_description"
    VIRTUAL_BUILDERTAGS_PROP = "virtual_builder_tags"
    workdir = "build"
    build_status = None
    reason = "changes"
    finished = False
    results = None
    stopped = False
    set_runtime_properties = True
    subs = None

    _sentinel = []  # used as a sentinel to indicate unspecified initial_value

    def __init__(self, requests):
        self.requests = requests
        self.locks = []
        # build a source stamp
        self.sources = requests[0].mergeSourceStampsWith(requests[1:])
        self.reason = requests[0].mergeReasons(requests[1:])

        self.currentStep = None
        self.workerEnvironment = {}
        self.buildid = None
        self.number = None
        self.executedSteps = []
        self.stepnames = {}

        self.terminate = False

        self._acquiringLock = None
        self._builderid = None
        # overall results, may downgrade after each step
        self.results = SUCCESS
        self.properties = properties.Properties()

        # tracks execution during the build finish phase
        self._locks_released = False
        self._build_finished = False

        # tracks the config version for locks
        self.config_version = None

    def setBuilder(self, builder):
        """
        Set the given builder as our builder.

        @type  builder: L{buildbot.process.builder.Builder}
        """
        self.builder = builder
        self.master = builder.master
        self.config_version = builder.config_version

    @defer.inlineCallbacks
    def setLocks(self, lockList):
        self.locks = yield self.builder.botmaster.getLockFromLockAccesses(lockList,
                                                                          self.config_version)

    def setWorkerEnvironment(self, env):
        # TODO: remove once we don't have anything depending on this method or attribute
        # e.g., old-style steps (ShellMixin pulls the environment out of the
        # builder directly)
        self.workerEnvironment = env

    def getSourceStamp(self, codebase=''):
        for source in self.sources:
            if source.codebase == codebase:
                return source
        return None

    def getAllSourceStamps(self):
        return list(self.sources)

    @staticmethod
    def allChangesFromSources(sources):
        for s in sources:
            for c in s.changes:
                yield c

    def allChanges(self):
        return Build.allChangesFromSources(self.sources)

    def allFiles(self):
        # return a list of all source files that were changed
        files = []
        for c in self.allChanges():
            for f in c.files:
                files.append(f)
        return files

    def __repr__(self):
        return "<Build %s number:%r results:%s>" % (
            self.builder.name, self.number, statusToString(self.results))

    def blamelist(self):
        # Note that this algorithm is also implemented in buildbot.reporters.utils.getResponsibleUsersForBuild,
        # but using the data api.
        # it is important for the UI to have the blamelist easily available.
        # The best way is to make sure the owners property is set to full blamelist
        blamelist = []
        for c in self.allChanges():
            if c.who not in blamelist:
                blamelist.append(c.who)
        for source in self.sources:
            if source.patch:  # Add patch author to blamelist
                blamelist.append(source.patch_info[0])
        blamelist.sort()
        return blamelist

    def changesText(self):
        changetext = ""
        for c in self.allChanges():
            changetext += "-" * 60 + "\n\n" + c.asText() + "\n"
        # consider sorting these by number
        return changetext

    def setStepFactories(self, step_factories):
        """Set a list of 'step factories', which are tuples of (class,
        kwargs), where 'class' is generally a subclass of step.BuildStep .
        These are used to create the Steps themselves when the Build starts
        (as opposed to when it is first created). By creating the steps
        later, their __init__ method will have access to things like
        build.allFiles() ."""
        self.stepFactories = list(step_factories)

    useProgress = True

    def getWorkerCommandVersion(self, command, oldversion=None):
        return self.workerforbuilder.getWorkerCommandVersion(command, oldversion)

    def getWorkerName(self):
        return self.workerforbuilder.worker.workername

    @staticmethod
    def setupPropertiesKnownBeforeBuildStarts(props, requests, builder,
                                              workerforbuilder):
        # Note that this function does not setup the 'builddir' worker property
        # It's not possible to know it until before the actual worker has
        # attached.

        # start with global properties from the configuration
        props.updateFromProperties(builder.master.config.properties)

        # from the SourceStamps, which have properties via Change
        sources = requests[0].mergeSourceStampsWith(requests[1:])
        for change in Build.allChangesFromSources(sources):
            props.updateFromProperties(change.properties)

        # get any properties from requests (this is the path through which
        # schedulers will send us properties)
        for rq in requests:
            props.updateFromProperties(rq.properties)

        # get builder properties
        builder.setupProperties(props)

        # get worker properties
        # navigate our way back to the L{buildbot.worker.Worker}
        # object that came from the config, and get its properties
        workerforbuilder.worker.setupProperties(props)

    def setupOwnProperties(self):
        # now set some properties of our own, corresponding to the
        # build itself
        props = self.getProperties()
        props.setProperty("buildnumber", self.number, "Build")

        if self.sources and len(self.sources) == 1:
            # old interface for backwards compatibility
            source = self.sources[0]
            props.setProperty("branch", source.branch, "Build")
            props.setProperty("revision", source.revision, "Build")
            props.setProperty("repository", source.repository, "Build")
            props.setProperty("codebase", source.codebase, "Build")
            props.setProperty("project", source.project, "Build")

    def setupWorkerBuildirProperty(self, workerforbuilder):
        path_module = workerforbuilder.worker.path_module

        # navigate our way back to the L{buildbot.worker.Worker}
        # object that came from the config, and get its properties
        if workerforbuilder.worker.worker_basedir:
            builddir = path_module.join(
                bytes2unicode(workerforbuilder.worker.worker_basedir),
                bytes2unicode(self.builder.config.workerbuilddir))
            self.setProperty("builddir", builddir, "Worker")

    def setupWorkerForBuilder(self, workerforbuilder):
        self.path_module = workerforbuilder.worker.path_module
        self.workername = workerforbuilder.worker.workername
        self.build_status.setWorkername(self.workername)

    @defer.inlineCallbacks
    def getBuilderId(self):
        if self._builderid is None:
            if self.hasProperty(self.VIRTUAL_BUILDERNAME_PROP):
                self._builderid = yield self.builder.getBuilderIdForName(
                    self.getProperty(self.VIRTUAL_BUILDERNAME_PROP))
                description = self.getProperty(
                    self.VIRTUAL_BUILDERDESCRIPTION_PROP,
                    self.builder.config.description)
                tags = self.getProperty(
                    self.VIRTUAL_BUILDERTAGS_PROP,
                    self.builder.config.tags)
                if type(tags) == type([]) and '_virtual_' not in tags:
                    tags.append('_virtual_')

                self.master.data.updates.updateBuilderInfo(self._builderid,
                                                           description,
                                                           tags)

            else:
                self._builderid = yield self.builder.getBuilderId()
        return self._builderid

    @defer.inlineCallbacks
    def startBuild(self, build_status, workerforbuilder):
        """This method sets up the build, then starts it by invoking the
        first Step. It returns a Deferred which will fire when the build
        finishes. This Deferred is guaranteed to never errback."""
        self.workerforbuilder = workerforbuilder
        self.conn = None

        worker = workerforbuilder.worker

        log.msg("%s.startBuild" % self)

        self.build_status = build_status
        # TODO: this will go away when build collapsing is implemented; until
        # then we just assign the build to the first buildrequest
        brid = self.requests[0].id
        builderid = yield self.getBuilderId()
        self.buildid, self.number = \
            yield self.master.data.updates.addBuild(
                builderid=builderid,
                buildrequestid=brid,
                workerid=worker.workerid)

        self.stopBuildConsumer = yield self.master.mq.startConsuming(self.controlStopBuild,
                                                                     ("control", "builds",
                                                                      str(self.buildid),
                                                                      "stop"))

        # the preparation step counts the time needed for preparing the worker and getting the locks.
        # we cannot use a real step as we don't have a worker yet.
        self.preparation_step = buildstep.BuildStep(name="worker_preparation")
        self.preparation_step.setBuild(self)
        yield self.preparation_step.addStep()
        self.setupOwnProperties()

        # then narrow WorkerLocks down to the right worker
        self.locks = [(l.getLockForWorker(workerforbuilder.worker.workername),
                       a)
                      for l, a in self.locks]
        metrics.MetricCountEvent.log('active_builds', 1)

        # make sure properties are available to people listening on 'new'
        # events
        yield self._flushProperties(None)
        self.build_status.buildStarted(self)
        yield self.master.data.updates.setBuildStateString(self.buildid, 'starting')
        yield self.master.data.updates.generateNewBuildEvent(self.buildid)

        try:
            self.setupBuild()  # create .steps
        except Exception:
            yield self.buildPreparationFailure(Failure(), "setupBuild")
            self.buildFinished(['Build.setupBuild', 'failed'], EXCEPTION)
            return

        # flush properties in the beginning of the build
        yield self._flushProperties(None)

        yield self.master.data.updates.setBuildStateString(self.buildid,
                                                           'preparing worker')
        try:
            ready_or_failure = yield workerforbuilder.prepare(self)
        except Exception:
            ready_or_failure = Failure()

        # If prepare returns True then it is ready and we start a build
        # If it returns failure then we don't start a new build.
        if ready_or_failure is not True:
            yield self.buildPreparationFailure(ready_or_failure, "worker_prepare")
            if self.stopped:
                self.buildFinished(["worker", "cancelled"], self.results)
            elif isinstance(ready_or_failure, Failure) and ready_or_failure.check(interfaces.LatentWorkerCannotSubstantiate):
                self.buildFinished(["worker", "cannot", "substantiate"], EXCEPTION)
            else:
                self.buildFinished(["worker", "not", "available"], RETRY)
            return

        # ping the worker to make sure they're still there. If they've
        # fallen off the map (due to a NAT timeout or something), this
        # will fail in a couple of minutes, depending upon the TCP
        # timeout.
        #
        # TODO: This can unnecessarily suspend the starting of a build, in
        # situations where the worker is live but is pushing lots of data to
        # us in a build.
        yield self.master.data.updates.setBuildStateString(self.buildid,
                                                           'pinging worker')
        log.msg("starting build %s.. pinging the worker %s"
                % (self, workerforbuilder))
        try:
            ping_success_or_failure = yield workerforbuilder.ping()
        except Exception:
            ping_success_or_failure = Failure()

        if ping_success_or_failure is not True:
            yield self.buildPreparationFailure(ping_success_or_failure, "worker_ping")
            self.buildFinished(["worker", "not", "pinged"], RETRY)
            return

        self.conn = workerforbuilder.worker.conn

        # To retrieve the builddir property, the worker must be attached as we
        # depend on its path_module. Latent workers become attached only after
        # preparing them, so we can't setup the builddir property earlier like
        # the rest of properties
        self.setupWorkerBuildirProperty(workerforbuilder)
        self.setupWorkerForBuilder(workerforbuilder)
        self.subs = self.conn.notifyOnDisconnect(self.lostRemote)

        # tell the remote that it's starting a build, too
        try:
            yield self.conn.remoteStartBuild(self.builder.name)
        except Exception:
            yield self.buildPreparationFailure(Failure(), "start_build")
            self.buildFinished(["worker", "not", "building"], RETRY)
            return

        yield self.master.data.updates.setBuildStateString(self.buildid,
                                                           'acquiring locks')
        yield self.acquireLocks()
        yield self.master.data.updates.setStepStateString(self.preparation_step.stepid,
                                                          "worker ready")
        yield self.master.data.updates.finishStep(self.preparation_step.stepid, SUCCESS, False)

        yield self.master.data.updates.setBuildStateString(self.buildid,
                                                           'building')

        # start the sequence of steps
        self.startNextStep()

    @defer.inlineCallbacks
    def buildPreparationFailure(self, why, state_string):
        log.err(why, "while " + state_string)
        self.workerforbuilder.worker.putInQuarantine()
        if isinstance(why, failure.Failure):
            yield self.preparation_step.addLogWithFailure(why)
        yield self.master.data.updates.setStepStateString(self.preparation_step.stepid,
                                                          "error while " + state_string)
        yield self.master.data.updates.finishStep(self.preparation_step.stepid, EXCEPTION, False)

    @staticmethod
    def _canAcquireLocks(lockList, workerforbuilder):
        for lock, access in lockList:
            worker_lock = lock.getLockForWorker(
                workerforbuilder.worker.workername)
            if not worker_lock.isAvailable(None, access):
                return False
        return True

    def acquireLocks(self, res=None):
        self._acquiringLock = None
        if not self.locks:
            return defer.succeed(None)
        if self.stopped:
            return defer.succeed(None)
        log.msg("acquireLocks(build %s, locks %s)" % (self, self.locks))
        for lock, access in self.locks:
            if not lock.isAvailable(self, access):
                log.msg("Build %s waiting for lock %s" % (self, lock))
                d = lock.waitUntilMaybeAvailable(self, access)
                d.addCallback(self.acquireLocks)
                self._acquiringLock = (lock, access, d)
                return d
        # all locks are available, claim them all
        for lock, access in self.locks:
            lock.claim(self, access)
        return defer.succeed(None)

    def setUniqueStepName(self, step):
        # If there are any name collisions, we add a count to the loser
        # until it is unique.
        name = step.name
        if name in self.stepnames:
            count = self.stepnames[name]
            count += 1
            self.stepnames[name] = count
            name = "%s_%d" % (step.name, count)
        else:
            self.stepnames[name] = 0
        step.name = name

    def setupBuildSteps(self, step_factories):
        steps = []
        for factory in step_factories:
            step = factory.buildStep()
            step.setBuild(self)
            step.setWorker(self.workerforbuilder.worker)
            self.setUniqueStepName(step)
            steps.append(step)

            if self.useProgress:
                step.setupProgress()
        return steps

    def setupBuild(self):
        # create the actual BuildSteps.

        self.steps = self.setupBuildSteps(self.stepFactories)

        owners = set(self.blamelist())
        # gather owners from build requests
        owners.update({r.properties['owner'] for r in self.requests
                       if "owner" in r.properties})
        if owners:
            self.setProperty('owners', sorted(owners), 'Build')
        self.text = []  # list of text string lists (text2)

    def _addBuildSteps(self, step_factories):
        factories = [interfaces.IBuildStepFactory(s) for s in step_factories]
        return self.setupBuildSteps(factories)

    def addStepsAfterCurrentStep(self, step_factories):
        # Add the new steps after the step that is running.
        # The running step has already been popped from self.steps
        self.steps[0:0] = self._addBuildSteps(step_factories)

    def addStepsAfterLastStep(self, step_factories):
        # Add the new steps to the end.
        self.steps.extend(self._addBuildSteps(step_factories))

    def getNextStep(self):
        """This method is called to obtain the next BuildStep for this build.
        When it returns None (or raises a StopIteration exception), the build
        is complete."""
        if not self.steps:
            return None
        if not self.conn:
            return None
        if self.terminate or self.stopped:
            # Run any remaining alwaysRun steps, and skip over the others
            while True:
                s = self.steps.pop(0)
                if s.alwaysRun:
                    return s
                if not self.steps:
                    return None
        else:
            return self.steps.pop(0)

    def startNextStep(self):
        try:
            s = self.getNextStep()
        except StopIteration:
            s = None
        if not s:
            return self.allStepsDone()
        self.executedSteps.append(s)
        self.currentStep = s
        d = defer.maybeDeferred(s.startStep, self.conn)
        d.addBoth(self._flushProperties)
        d.addCallback(self._stepDone, s)
        d.addErrback(self.buildException)

    @defer.inlineCallbacks
    def _flushProperties(self, results):
        # `results` is just passed on to the next callback
        yield self.master.data.updates.setBuildProperties(self.buildid, self)

        return results

    @defer.inlineCallbacks
    def _stepDone(self, results, step):
        self.currentStep = None
        if self.finished:
            return  # build was interrupted, don't keep building
        terminate = yield self.stepDone(results, step)  # interpret/merge results
        if terminate:
            self.terminate = True
        yield self.startNextStep()

    @defer.inlineCallbacks
    def stepDone(self, results, step):
        """This method is called when the BuildStep completes. It is passed a
        status object from the BuildStep and is responsible for merging the
        Step's results into those of the overall Build."""

        terminate = False
        text = None
        if isinstance(results, tuple):
            results, text = results
        assert isinstance(results, type(SUCCESS)), "got %r" % (results,)
        summary = yield step.getBuildResultSummary()
        if 'build' in summary:
            text = [summary['build']]
        log.msg(" step '%s' complete: %s (%s)" % (step.name, statusToString(results), text))
        if text:
            self.text.extend(text)
            self.master.data.updates.setBuildStateString(self.buildid,
                                                         bytes2unicode(" ".join(self.text)))
        self.results, terminate = computeResultAndTermination(step, results,
                                                              self.results)
        if not self.conn:
            # force the results to retry if the connection was lost
            self.results = RETRY
            terminate = True
        return terminate

    def lostRemote(self, conn=None):
        # the worker went away. There are several possible reasons for this,
        # and they aren't necessarily fatal. For now, kill the build, but
        # TODO: see if we can resume the build when it reconnects.
        log.msg("%s.lostRemote" % self)
        self.conn = None
        self.text = ["lost", "connection"]
        self.results = RETRY
        if self.currentStep and self.currentStep.results is None:
            # this should cause the step to finish.
            log.msg(" stopping currentStep", self.currentStep)
            self.currentStep.interrupt(Failure(error.ConnectionLost()))
        else:
            self.text = ["lost", "connection"]
            self.stopped = True
            if self._acquiringLock:
                lock, access, d = self._acquiringLock
                lock.stopWaitingUntilAvailable(self, access, d)

    def controlStopBuild(self, key, params):
        return self.stopBuild(**params)

    def stopBuild(self, reason="<no reason given>", results=CANCELLED):
        # the idea here is to let the user cancel a build because, e.g.,
        # they realized they committed a bug and they don't want to waste
        # the time building something that they know will fail. Another
        # reason might be to abandon a stuck build. We want to mark the
        # build as failed quickly rather than waiting for the worker's
        # timeout to kill it on its own.

        log.msg(" %s: stopping build: %s %d" % (self, reason, results))
        if self.finished:
            return
        # TODO: include 'reason' in this point event
        self.stopped = True
        if self.currentStep and self.currentStep.results is None:
            self.currentStep.interrupt(reason)

        self.results = results

        if self._acquiringLock:
            lock, access, d = self._acquiringLock
            lock.stopWaitingUntilAvailable(self, access, d)

    def allStepsDone(self):
        if self.results == FAILURE:
            text = ["failed"]
        elif self.results == WARNINGS:
            text = ["warnings"]
        elif self.results == EXCEPTION:
            text = ["exception"]
        elif self.results == RETRY:
            text = ["retry"]
        elif self.results == CANCELLED:
            text = ["cancelled"]
        else:
            text = ["build", "successful"]
        text.extend(self.text)
        return self.buildFinished(text, self.results)

    def buildException(self, why):
        log.msg("%s.buildException" % self)
        log.err(why)
        # try to finish the build, but since we've already faced an exception,
        # this may not work well.
        try:
            self.buildFinished(["build", "exception"], EXCEPTION)
        except Exception:
            log.err(Failure(), 'while finishing a build with an exception')

    @defer.inlineCallbacks
    def buildFinished(self, text, results):
        """This method must be called when the last Step has completed. It
        marks the Build as complete and returns the Builder to the 'idle'
        state.

        It takes two arguments which describe the overall build status:
        text, results. 'results' is one of the possible results (see buildbot.process.results).

        If 'results' is SUCCESS or WARNINGS, we will permit any dependent
        builds to start. If it is 'FAILURE', those builds will be
        abandoned."""
        try:
            self.stopBuildConsumer.stopConsuming()
            self.finished = True
            if self.conn:
                self.subs.unsubscribe()
                self.subs = None
                self.conn = None
            log.msg(" %s: build finished" % self)
            self.results = worst_status(self.results, results)
            self.build_status.setText(text)
            self.build_status.setResults(self.results)
            self.build_status.buildFinished()
            eventually(self.releaseLocks)
            metrics.MetricCountEvent.log('active_builds', -1)

            yield self.master.data.updates.setBuildStateString(self.buildid,
                                                               bytes2unicode(" ".join(text)))
            yield self.master.data.updates.finishBuild(self.buildid, self.results)

            if self.results == EXCEPTION:
                # When a build has an exception, put the worker in quarantine for a few seconds
                # to make sure we try next build with another worker
                self.workerforbuilder.worker.putInQuarantine()
            elif self.results != RETRY:
                # This worker looks sane if status is neither retry or exception

                # Avoid a race in case the build step reboot the worker
                if self.workerforbuilder.worker is not None:
                    self.workerforbuilder.worker.resetQuarantine()

            # mark the build as finished
            self.workerforbuilder.buildFinished()
            self.builder.buildFinished(self, self.workerforbuilder)

            self._tryScheduleBuildsAfterLockUnlock(build_finished=True)
        except Exception:
            log.err(None, 'from finishing a build; this is a '
                          'serious error - please file a bug at http://buildbot.net')

    def releaseLocks(self):
        if self.locks:
            log.msg("releaseLocks(%s): %s" % (self, self.locks))

        for lock, access in self.locks:
            if lock.isOwner(self, access):
                lock.release(self, access)

        self._tryScheduleBuildsAfterLockUnlock(locks_released=True)

    def _tryScheduleBuildsAfterLockUnlock(self, locks_released=False,
                                          build_finished=False):
        # we need to inform the botmaster to attempt to schedule any pending
        # build request if we released any locks. This is because buildrequest
        # may be started for a completely unrelated builder and yet depend on
        # a lock released by this build.
        #
        # TODO: the current approach is dumb as we just attempt to schedule
        # all buildrequests. A much better idea would be to record the reason
        # of why a buildrequest was not scheduled in the BuildRequestDistributor
        # and then attempt to schedule only these buildrequests which may have
        # had that reason resolved.

        # this function is complicated by the fact that the botmaster must be
        # informed only when all locks have been released and the actions in
        # buildFinished have concluded. Since releaseLocks is called using
        # eventually this may happen in any order.
        self._locks_released = self._locks_released or locks_released
        self._build_finished = self._build_finished or build_finished

        if not self.locks:
            return

        if self._locks_released and self._build_finished:
            self.builder.botmaster.maybeStartBuildsForAllBuilders()

    def getSummaryStatistic(self, name, summary_fn, initial_value=_sentinel):
        step_stats_list = [
            st.getStatistic(name)
            for st in self.executedSteps
            if st.hasStatistic(name)]
        if initial_value is self._sentinel:
            return reduce(summary_fn, step_stats_list)
        return reduce(summary_fn, step_stats_list, initial_value)

    @defer.inlineCallbacks
    def getUrl(self):
        builder_id = yield self.getBuilderId()
        return getURLForBuild(self.master, builder_id, self.number)

    def waitUntilFinished(self):
        return self.master.mq.waitUntilEvent(
            ('builds', str(self.buildid), 'finished'),
            lambda: self.finished)

    def getWorkerInfo(self):
        return self.workerforbuilder.worker.worker_status.info

    # IBuildControl

    def getStatus(self):
        return self.build_status

    # stopBuild is defined earlier


components.registerAdapter(
    lambda build: interfaces.IProperties(build.properties),
    Build, interfaces.IProperties)
