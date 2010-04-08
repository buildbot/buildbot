# -*- test-case-name: buildbot.test.test_step -*-

import types

from zope.interface import implements
from twisted.python import log
from twisted.python.failure import Failure
from twisted.internet import reactor, defer, error

from buildbot import interfaces, locks
from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, EXCEPTION, RETRY
from buildbot.status.builder import Results
from buildbot.status.progress import BuildProgress


class Build:
    """I represent a single build by a single slave. Specialized Builders can
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
    @ivar build_status: the L{buildbot.status.builder.BuildStatus} that
                        collects our status
    """

    implements(interfaces.IBuildControl)

    workdir = "build"
    build_status = None
    reason = "changes"
    finished = False
    results = None
    stopped = False

    def __init__(self, requests):
        self.requests = requests
        for req in self.requests:
            req.startCount += 1
        self.locks = []
        # build a source stamp
        self.source = requests[0].mergeWith(requests[1:])
        self.reason = requests[0].mergeReasons(requests[1:])

        self.progress = None
        self.currentStep = None
        self.slaveEnvironment = {}

        self.terminate = False

    def setBuilder(self, builder):
        """
        Set the given builder as our builder.

        @type  builder: L{buildbot.process.builder.Builder}
        """
        self.builder = builder

    def setLocks(self, locks):
        self.locks = locks

    def setSlaveEnvironment(self, env):
        self.slaveEnvironment = env

    def getSourceStamp(self):
        return self.source

    def setProperty(self, propname, value, source):
        """Set a property on this build. This may only be called after the
        build has started, so that it has a BuildStatus object where the
        properties can live."""
        self.build_status.setProperty(propname, value, source)

    def getProperties(self):
        return self.build_status.getProperties()

    def getProperty(self, propname):
        return self.build_status.getProperty(propname)

    def allChanges(self):
        return self.source.changes

    def allFiles(self):
        # return a list of all source files that were changed
        files = []
        for c in self.allChanges():
            for f in c.files:
                files.append(f)
        return files

    def __repr__(self):
        return "<Build %s>" % (self.builder.name,)

    def blamelist(self):
        blamelist = []
        for c in self.allChanges():
            if c.who not in blamelist:
                blamelist.append(c.who)
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

    def getSlaveCommandVersion(self, command, oldversion=None):
        return self.slavebuilder.getSlaveCommandVersion(command, oldversion)
    def getSlaveName(self):
        return self.slavebuilder.slave.slavename

    def setupProperties(self):
        props = self.getProperties()

        # start with global properties from the configuration
        buildmaster = self.builder.botmaster.parent
        props.updateFromProperties(buildmaster.properties)

        # get any properties from requests (this is the path through
        # which schedulers will send us properties)
        for rq in self.requests:
            props.updateFromProperties(rq.properties)

        # and finally, from the SourceStamp, which has properties via Change
        for change in self.source.changes:
            props.updateFromProperties(change.properties)

        # now set some properties of our own, corresponding to the
        # build itself
        props.setProperty("buildnumber", self.build_status.number, "Build")
        props.setProperty("branch", self.source.branch, "Build")
        props.setProperty("revision", self.source.revision, "Build")
        props.setProperty("repository", self.source.repository, "Build")
        props.setProperty("project", self.source.project, "Build")
        self.builder.setupProperties(props)

    def setupSlaveBuilder(self, slavebuilder):
        self.slavebuilder = slavebuilder

        # navigate our way back to the L{buildbot.buildslave.BuildSlave}
        # object that came from the config, and get its properties
        buildslave_properties = slavebuilder.slave.properties
        self.getProperties().updateFromProperties(buildslave_properties)

        self.slavename = slavebuilder.slave.slavename
        self.build_status.setSlavename(self.slavename)

    def startBuild(self, build_status, expectations, slavebuilder):
        """This method sets up the build, then starts it by invoking the
        first Step. It returns a Deferred which will fire when the build
        finishes. This Deferred is guaranteed to never errback."""

        # we are taking responsibility for watching the connection to the
        # remote. This responsibility was held by the Builder until our
        # startBuild was called, and will not return to them until we fire
        # the Deferred returned by this method.

        log.msg("%s.startBuild" % self)
        self.build_status = build_status
        # now that we have a build_status, we can set properties
        self.setupProperties()
        self.setupSlaveBuilder(slavebuilder)
        slavebuilder.slave.updateSlaveStatus(buildStarted=build_status)

        # convert all locks into their real forms
        lock_list = []
        for access in self.locks:
            if not isinstance(access, locks.LockAccess):
                # Buildbot 0.7.7 compability: user did not specify access
                access = access.defaultAccess()
            lock = self.builder.botmaster.getLockByID(access.lockid)
            lock_list.append((lock, access))
        self.locks = lock_list
        # then narrow SlaveLocks down to the right slave
        self.locks = [(l.getLock(self.slavebuilder), la)
                       for l, la in self.locks]
        self.remote = slavebuilder.remote
        self.remote.notifyOnDisconnect(self.lostRemote)
        d = self.deferred = defer.Deferred()
        def _release_slave(res, slave, bs):
            self.slavebuilder.buildFinished()
            slave.updateSlaveStatus(buildFinished=bs)
            return res
        d.addCallback(_release_slave, self.slavebuilder.slave, build_status)

        try:
            self.setupBuild(expectations) # create .steps
        except:
            # the build hasn't started yet, so log the exception as a point
            # event instead of flunking the build. 
            # TODO: associate this failure with the build instead. 
            # this involves doing
            # self.build_status.buildStarted() from within the exception
            # handler
            log.msg("Build.setupBuild failed")
            log.err(Failure())
            self.builder.builder_status.addPointEvent(["setupBuild",
                                                       "exception"])
            self.finished = True
            self.results = FAILURE
            self.deferred = None
            d.callback(self)
            return d

        self.acquireLocks().addCallback(self._startBuild_2)
        return d

    def acquireLocks(self, res=None):
        log.msg("acquireLocks(step %s, locks %s)" % (self, self.locks))
        if not self.locks:
            return defer.succeed(None)
        for lock, access in self.locks:
            if not lock.isAvailable(access):
                log.msg("Build %s waiting for lock %s" % (self, lock))
                d = lock.waitUntilMaybeAvailable(self, access)
                d.addCallback(self.acquireLocks)
                return d
        # all locks are available, claim them all
        for lock, access in self.locks:
            lock.claim(self, access)
        return defer.succeed(None)

    def _startBuild_2(self, res):
        self.build_status.buildStarted(self)
        self.startNextStep()

    def setupBuild(self, expectations):
        # create the actual BuildSteps. If there are any name collisions, we
        # add a count to the loser until it is unique.
        self.steps = []
        self.stepStatuses = {}
        stepnames = {}
        sps = []

        for factory, args in self.stepFactories:
            args = args.copy()
            try:
                step = factory(**args)
            except:
                log.msg("error while creating step, factory=%s, args=%s"
                        % (factory, args))
                raise
            step.setBuild(self)
            step.setBuildSlave(self.slavebuilder.slave)
            if callable (self.workdir):
                step.setDefaultWorkdir (self.workdir (self.source))
            else:
                step.setDefaultWorkdir (self.workdir)
            name = step.name
            if stepnames.has_key(name):
                count = stepnames[name]
                count += 1
                stepnames[name] = count
                name = step.name + "_%d" % count
            else:
                stepnames[name] = 0
            step.name = name
            self.steps.append(step)

            # tell the BuildStatus about the step. This will create a
            # BuildStepStatus and bind it to the Step.
            step_status = self.build_status.addStepWithName(name)
            step.setStepStatus(step_status)

            sp = None
            if self.useProgress:
                # XXX: maybe bail if step.progressMetrics is empty? or skip
                # progress for that one step (i.e. "it is fast"), or have a
                # separate "variable" flag that makes us bail on progress
                # tracking
                sp = step.setupProgress()
            if sp:
                sps.append(sp)

        # Create a buildbot.status.progress.BuildProgress object. This is
        # called once at startup to figure out how to build the long-term
        # Expectations object, and again at the start of each build to get a
        # fresh BuildProgress object to track progress for that individual
        # build. TODO: revisit at-startup call

        if self.useProgress:
            self.progress = BuildProgress(sps)
            if self.progress and expectations:
                self.progress.setExpectationsFrom(expectations)

        # we are now ready to set up our BuildStatus.
        self.build_status.setSourceStamp(self.source)
        self.build_status.setReason(self.reason)
        self.build_status.setBlamelist(self.blamelist())
        self.build_status.setProgress(self.progress)

        # gather owners from build requests
        owners = [r.properties['owner'] for r in self.requests
                  if r.properties.has_key('owner')]
        if owners: self.setProperty('owners', owners, self.reason)

        self.results = [] # list of FAILURE, SUCCESS, WARNINGS, SKIPPED
        self.result = SUCCESS # overall result, may downgrade after each step
        self.text = [] # list of text string lists (text2)

    def getNextStep(self):
        """This method is called to obtain the next BuildStep for this build.
        When it returns None (or raises a StopIteration exception), the build
        is complete."""
        if self.stopped:
            return None
        if not self.steps:
            return None
        if self.terminate:
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
        self.currentStep = s
        d = defer.maybeDeferred(s.startStep, self.remote)
        d.addCallback(self._stepDone, s)
        d.addErrback(self.buildException)

    def _stepDone(self, results, step):
        self.currentStep = None
        if self.finished:
            return # build was interrupted, don't keep building
        terminate = self.stepDone(results, step) # interpret/merge results
        if terminate:
            self.terminate = True
        return self.startNextStep()

    def stepDone(self, result, step):
        """This method is called when the BuildStep completes. It is passed a
        status object from the BuildStep and is responsible for merging the
        Step's results into those of the overall Build."""

        terminate = False
        text = None
        if type(result) == types.TupleType:
            result, text = result
        assert type(result) == type(SUCCESS)
        log.msg(" step '%s' complete: %s" % (step.name, Results[result]))
        self.results.append(result)
        if text:
            self.text.extend(text)
        if not self.remote:
            terminate = True
        if result == FAILURE:
            if step.warnOnFailure:
                if self.result != FAILURE:
                    self.result = WARNINGS
            if step.flunkOnFailure:
                self.result = FAILURE
            if step.haltOnFailure:
                terminate = True
        elif result == WARNINGS:
            if step.warnOnWarnings:
                if self.result != FAILURE:
                    self.result = WARNINGS
            if step.flunkOnWarnings:
                self.result = FAILURE
        elif result == EXCEPTION:
            self.result = EXCEPTION
            terminate = True
        elif result == RETRY:
            self.result = RETRY
            terminate = True
        return terminate

    def lostRemote(self, remote=None):
        # the slave went away. There are several possible reasons for this,
        # and they aren't necessarily fatal. For now, kill the build, but
        # TODO: see if we can resume the build when it reconnects.
        log.msg("%s.lostRemote" % self)
        self.remote = None
        if self.currentStep:
            # this should cause the step to finish.
            log.msg(" stopping currentStep", self.currentStep)
            self.currentStep.interrupt(Failure(error.ConnectionLost()))

    def stopBuild(self, reason="<no reason given>"):
        # the idea here is to let the user cancel a build because, e.g.,
        # they realized they committed a bug and they don't want to waste
        # the time building something that they know will fail. Another
        # reason might be to abandon a stuck build. We want to mark the
        # build as failed quickly rather than waiting for the slave's
        # timeout to kill it on its own.

        log.msg(" %s: stopping build: %s" % (self, reason))
        if self.finished:
            return
        # TODO: include 'reason' in this point event
        self.builder.builder_status.addPointEvent(['interrupt'])
        self.stopped = True
        self.currentStep.interrupt(reason)

    def allStepsDone(self):
        if self.result == FAILURE:
            text = ["failed"]
        elif self.result == WARNINGS:
            text = ["warnings"]
        elif self.result == EXCEPTION:
            text = ["exception"]
        else:
            text = ["build", "successful"]
        text.extend(self.text)
        return self.buildFinished(text, self.result)

    def buildException(self, why):
        log.msg("%s.buildException" % self)
        log.err(why)
        self.buildFinished(["build", "exception"], FAILURE)

    def buildFinished(self, text, results):
        """This method must be called when the last Step has completed. It
        marks the Build as complete and returns the Builder to the 'idle'
        state.

        It takes two arguments which describe the overall build status:
        text, results. 'results' is one of SUCCESS, WARNINGS, or FAILURE.

        If 'results' is SUCCESS or WARNINGS, we will permit any dependant
        builds to start. If it is 'FAILURE', those builds will be
        abandoned."""

        self.finished = True
        if self.remote:
            self.remote.dontNotifyOnDisconnect(self.lostRemote)
        self.results = results

        log.msg(" %s: build finished" % self)
        self.build_status.setText(text)
        self.build_status.setResults(results)
        self.build_status.buildFinished()
        if self.progress and results == SUCCESS:
            # XXX: also test a 'timing consistent' flag?
            log.msg(" setting expectations for next time")
            self.builder.setExpectations(self.progress)
        reactor.callLater(0, self.releaseLocks)
        self.deferred.callback(self)
        self.deferred = None

    def releaseLocks(self):
        log.msg("releaseLocks(%s): %s" % (self, self.locks))
        for lock, access in self.locks:
            lock.release(self, access)

    # IBuildControl

    def getStatus(self):
        return self.build_status

    # stopBuild is defined earlier

