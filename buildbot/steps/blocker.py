from twisted.python import log, failure
from twisted.internet import defer, reactor

from buildbot.process.buildstep import BuildStep
from buildbot.status import builder

class BadStepError(Exception):
    """Raised by Blocker when it is passed an upstream step that cannot
    be found or is in a bad state."""
    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message

class Blocker(BuildStep):
    """
    Build step that blocks until at least one other step finishes.

    @ivar upstreamSteps: a non-empty list of (builderName, stepName) tuples
                         identifying the other build steps that must
                         complete in order to unblock this Blocker.
    @ivar idlePolicy: string: what to do if one of the upstream builders is
                      idle when this Blocker starts; one of:
                        \"error\": just blow up (the Blocker will fail with
                          status EXCEPTION)
                        \"ignore\": carry on as if the referenced build step
                          was not mentioned (or is already complete)
                        \"block\": block until the referenced builder starts
                          a build, and then block until the referenced build
                          step in that build finishes
    @ivar timeout: int: how long to block, in seconds, before giving up and
                   failing (default: None, meaning block forever)
    """
    parms = (BuildStep.parms +
             ['upstreamSteps',
              'idlePolicy',
              'timeout',
             ])

    flunkOnFailure = True               # override BuildStep's default
    upstreamSteps = None
    idlePolicy = "error"
    timeout = None

    VALID_IDLE_POLICIES = ("error", "ignore", "block")

    def __init__(self, **kwargs):
        BuildStep.__init__(self, **kwargs)
        if self.upstreamSteps is None:
            raise ValueError("you must supply upstreamSteps")
        if len(self.upstreamSteps) < 1:
            raise ValueError("upstreamSteps must be a non-empty list")
        if self.idlePolicy not in self.VALID_IDLE_POLICIES:
            raise ValueError(
                "invalid value for idlePolicy: %r (must be one of %s)"
                % (self.idlePolicy,
                   ", ".join(map(repr, self.VALID_IDLE_POLICIES))))

        # set of build steps (as BuildStepStatus objects) that we're
        # waiting on
        self._blocking_steps = set()

        # set of builders (as BuilderStatus objects) that have to start
        # a Build before we can block on one of their BuildSteps
        self._blocking_builders = set()

        self._overall_code = builder.SUCCESS # assume the best
        self._overall_text = []

        self._timer = None              # object returned by reactor.callLater()

    def _getBuildStatus(self, botmaster, builderName):
        try:
            # Get the buildbot.process.builder.Builder object for the
            # requested upstream builder: this is a long-lived object
            # that exists and has useful info in it whether or not a
            # build is currently running under it.
            builder = botmaster.builders[builderName]
        except KeyError:
            raise BadStepError(
                "no builder named %r" % builderName)

        # The Builder's BuilderStatus object is where we can find out
        # what's going on right now ... like, say, the list of
        # BuildStatus objects representing any builds running now.
        builderStatus = builder.builder_status
        current = builderStatus.getCurrentBuilds()

        if not current:
            msg = "builder %r is idle (no builds a-building)" % builderName
            if self.idlePolicy == "error":
                raise BadStepError(msg)
            elif self.idlePolicy == "ignore":
                # don't hang around waiting (assume the build has finished)
                log.msg("Blocker: " + msg + ": skipping it")
                return None
            elif self.idlePolicy == "block":
                log.msg("Blocker: " + msg + ": will block until it starts a build")
                self._blocking_builders.add(builderStatus)
                return None

            # N.B. when it comes time to look for last finished build,
            # e.g. to see if it finished less than N sec ago,
            # builderStatus.getLastFinishedBuild() could come
            # in handy

        # XXX what if there is more than one build a-building?
        buildStatus = current[0]
        log.msg("Blocker.start: found builder=%r, buildStatus=%r"
                % (builder, buildStatus))
        return buildStatus

    def _getStepStatus(self, buildStatus, stepName):
        for step_status in buildStatus.getSteps():
            if step_status.name == stepName:
                return step_status
        raise BadStepError(
            "builder %r has no step named %r"
            % (buildStatus.builder.name, stepName))

    def _getFullnames(self):
        if len(self.upstreamSteps) == 1:
            fullnames = ["(%s:%s)" % self.upstreamSteps[0]]
        else:
            fullnames = []
            fullnames.append("(%s:%s," % self.upstreamSteps[0])
            fullnames.extend(["%s:%s," % pair for pair in self.upstreamSteps[1:-1]])
            fullnames.append("%s:%s)" % self.upstreamSteps[-1])
        return fullnames

    def _getBlockingStatusText(self):
        return [self.name+":", "blocking on"] + self._getFullnames()

    def _getFinishStatusText(self, code, elapsed):
        meaning = builder.Results[code]
        text = [self.name+":",
                "upstream %s" % meaning,
                "after %.1f sec" % elapsed]
        if code != builder.SUCCESS:
            text += self._getFullnames()
        return text

    def _getTimeoutStatusText(self):
        return [self.name+":", "timed out", "(%.1f sec)" % self.timeout]

    def start(self):
        log.msg("Blocker.start: searching for steps %s" % "".join(self._getFullnames()))
        self.step_status.setText(self._getBlockingStatusText())

        log.msg("Blocker.start: self.timeout=%r" % self.timeout)
        if self.timeout is not None:
            self._timer = reactor.callLater(self.timeout, self._timeoutExpired)
        log.msg("Blocker.start: self._timer=%r" % self._timer)

        botmaster = self.build.slavebuilder.slave.parent
        stepStatuses = []               # list of BuildStepStatus objects
        errors = []                     # list of strings
        for (builderName, stepName) in self.upstreamSteps:
            buildStatus = stepStatus = None
            try:
                buildStatus = self._getBuildStatus(botmaster, builderName)
                if buildStatus is not None:
                    stepStatus = self._getStepStatus(buildStatus, stepName)
            except BadStepError, err:
                errors.append(err.message)
            if stepStatus is not None:
                # Make sure newly-discovered blocking steps are all
                # added to _blocking_steps before we subscribe to their
                # "finish" events!
                self._blocking_steps.add(stepStatus)

        if len(errors) == 1:
            raise BadStepError(errors[0])
        elif len(errors) > 1:
            raise BadStepError("multiple errors:\n" + "\n".join(errors))

        # Now we can register with each blocking step (BuildStepStatus
        # objects, actually) that we want a callback when the step
        # finishes.  Need to iterate over a copy of _blocking_steps
        # because it can be modified while we iterate: if any upstream
        # step is already finished, the _upstreamStepFinished() callback
        # will be called immediately.
        for stepStatus in self._blocking_steps.copy():
            self._awaitStepFinished(stepStatus)

        log.msg("Blocker: will block on %d steps: %r"
                % (len(self._blocking_steps), self._blocking_steps))
        if self._blocking_builders:
            log.msg("Blocker: will also block on %d builders starting a build: %r"
                    % (len(self._blocking_builders), self._blocking_builders))

        # Subscribe to each builder that we're waiting on to start.
        for bs in self._blocking_builders:
            bs.subscribe(BuilderStatusReceiver(self, bs))

    def _awaitStepFinished(self, stepStatus):
        # N.B. this will callback *immediately* (i.e. even before we
        # relinquish control to the reactor) if the upstream step in
        # question has already finished.
        d = stepStatus.waitUntilFinished()
        d.addCallback(self._upstreamStepFinished)

    def _timeoutExpired(self):
        log.msg("Blocker: timeout (%.1f sec) expired" % self.timeout)
        self.step_status.setColor("red")
        self.step_status.setText(self._getTimeoutStatusText())
        self.finished(builder.FAILURE)

    def _upstreamStepFinished(self, stepStatus):
        assert isinstance(stepStatus, builder.BuildStepStatus)
        log.msg("Blocker: build step %s:%s finished; stepStatus=%r"
                % (stepStatus.getBuild().builder.getName(),
                   stepStatus.getName(),
                   stepStatus.getResults()))

        (code, text) = stepStatus.getResults()
        if code != builder.SUCCESS and self._overall_code == builder.SUCCESS:
            # first non-SUCCESS result wins
            self._overall_code = code
        self._overall_text.extend(text)

        self._blocking_steps.remove(stepStatus)
        self._checkFinished()

    def _upstreamBuildStarted(self, builderStatus, receiver):
        assert isinstance(builderStatus, builder.BuilderStatus)
        builderStatus.unsubscribe(receiver)
        buildStatus = builderStatus.getCurrentBuilds()[0]
        log.msg("Blocker: builder %r (%r) started a build; buildStatus=%r"
                % (builderStatus, builderStatus.getName(), buildStatus))

        # Need to accumulate newly-discovered steps separately, so we
        # can add them to _blocking_steps en masse before subscribing to
        # their "finish" events.
        new_blocking_steps = []
        for (builderName, stepName) in self.upstreamSteps:
            if builderName == builderStatus.getName():
                try:
                    stepStatus = self._getStepStatus(buildStatus, stepName)
                except BadStepError, err:
                    self.failed(failure.Failure())
                    #log.err()
                    #self._overall_code = builder.EXCEPTION
                    #self._overall_text.append(str(err))
                else:
                    new_blocking_steps.append(stepStatus)

        self._blocking_steps.update(new_blocking_steps)
        for stepStatus in new_blocking_steps:
            self._awaitStepFinished(stepStatus)

        self._blocking_builders.remove(builderStatus)
        self._checkFinished()

    def _checkFinished(self):
        if self.step_status.isFinished():
            # this can happen if _upstreamBuildStarted() catches BadStepError
            # and fails the step
            log.msg("Blocker._checkFinished: already finished, so nothing to do here")
            return

        log.msg("Blocker._checkFinished: _blocking_steps=%r, _blocking_builders=%r"
                % (self._blocking_steps, self._blocking_builders))

        if not self._blocking_steps and not self._blocking_builders:
            if self.timeout:
                self._timer.cancel()

            self.finished(self._overall_code)
            self.step_status.setText2(self._overall_text)
            (start, finish) = self.step_status.getTimes()
            self.step_status.setText(
                self._getFinishStatusText(self._overall_code, finish - start))

class BuilderStatusReceiver:
    def __init__(self, blocker, builderStatus):
        # the Blocker step that wants to find out when a Builder starts
        # a Build
        self.blocker = blocker
        self.builderStatus = builderStatus

    def builderChangedState(self, *args):
        pass

    def buildStarted(self, name, buildStatus):
        log.msg("BuilderStatusReceiver: "
                "apparently, builder %r has started build %r"
                % (name, buildStatus))
        self.blocker._upstreamBuildStarted(self.builderStatus, self)

    def buildFinished(self, *args):
        pass
