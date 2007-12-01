from twisted.python import log, failure
from twisted.internet import defer
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
    """
    parms = BuildStep.parms + ['upstreamSteps']

    flunkOnFailure = True               # override BuildStep's default
    upstreamSteps = None

    def __init__(self, **kwargs):
        BuildStep.__init__(self, **kwargs)
        if self.upstreamSteps is None:
            raise ValueError("you must supply upstreamSteps")
        if len(self.upstreamSteps) < 1:
            raise ValueError("upstreamSteps must be a non-empty list")

        # what to do if an upstream builder is idle?
        #self.idlePolicy = "error"       # blow up
        #self.idlePolicy = "ignore"      # go right ahead (assume it has already run)
        self.idlePolicy = "block"       # wait until it has a build running

        # "full names" of the upstream steps (for status reporting)
        self._fullnames = ["%s:%s," % step for step in self.upstreamSteps]
        self._fullnames[-1] = self._fullnames[-1][:-1] # strip last comma

        # set of build steps (as BuildStepStatus objects) that we're
        # waiting on
        self._blocking_steps = set()

        # set of builders (as BuilderStatus objects) that have to start
        # a Build before we can block on one of their BuildSteps
        self._blocking_builders = set()

        self._overall_code = builder.SUCCESS # assume the best
        self._overall_text = []

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
            msg = "no builds building in builder %r" % builderName
            if self.idlePolicy == "error":
                raise BadStepError(msg)
            elif self.idlePolicy == "ignore":
                # don't hang around waiting (assume the build has finished)
                log.msg("Blocker: " + msg + ": skipping it")
                return None
            elif self.idlePolicy == "block":
                if builderStatus not in self._blocking_builders:
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

    def start(self):
        log.msg("Blocker.start: searching for steps %s" % "".join(self._fullnames))
        self.step_status.setText(["blocking on"] + self._fullnames)

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
                stepStatuses.append(stepStatus)

        if len(errors) == 1:
            raise BadStepError(errors[0])
        elif len(errors) > 1:
            raise BadStepError("multiple errors:\n" + "\n".join(errors))

        for stepStatus in stepStatuses:
            # Register with each blocking BuildStepStatus that we
            # want a callback when the step finishes.
            self._addBlockingStep(stepStatus)

        log.msg("Blocker: will block on %d steps: %r"
                % (len(self._blocking_steps), self._blocking_steps))
        if self._blocking_builders:
            log.msg("Blocker: will also block on %d builders starting a build: %r"
                    % (len(self._blocking_builders), self._blocking_builders))

        # Subscribe to each builder that we're waiting on to start.
        for bs in self._blocking_builders:
            bs.subscribe(BuilderStatusReceiver(self, bs))

    def _addBlockingStep(self, stepStatus):
        self._blocking_steps.add(stepStatus)
        d = stepStatus.waitUntilFinished()
        d.addCallback(self._upstreamStepFinished)

    def _upstreamStepFinished(self, results):
        assert isinstance(results, builder.BuildStepStatus)
        log.msg("Blocker: build step %r:%r finished; results=%r"
                % (results.getBuild().builder.getName(),
                   results.getName(),
                   results.getResults()))

        (code, text) = results.getResults()
        if code != builder.SUCCESS and self._overall_code == builder.SUCCESS:
            # first non-SUCCESS result wins
            self._overall_code = code
        self._overall_text.extend(text)

        self._blocking_steps.remove(results)
        self._checkFinished()

    def _upstreamBuildStarted(self, builderStatus, receiver):
        assert isinstance(builderStatus, builder.BuilderStatus)
        builderStatus.unsubscribe(receiver)
        buildStatus = builderStatus.getCurrentBuilds()[0]
        log.msg("Blocker: builder %r (%r) started a build; buildStatus=%r"
                % (builderStatus, builderStatus.getName(), buildStatus))

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
                    self._addBlockingStep(stepStatus)

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
            fullnames = self._fullnames[:]
            fullnames[-1] += ":"
            self.step_status.setText(fullnames + [builder.Results[self._overall_code]])
            self.finished((self._overall_code, self._overall_text))

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
