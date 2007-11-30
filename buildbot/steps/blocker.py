from twisted.python import log
from twisted.internet import defer
from buildbot.process.buildstep import BuildStep

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
        self.idlePolicy = "error"       # blow up
        #self.idlePolicy = "ignore"      # go right ahead (assume it has already run)
        #self.idlePolicy = "block"       # wait until it has a build running

        # "full names" of the upstream steps (for status reporting)
        self._fullnames = ["%s:%s," % step for step in self.upstreamSteps]
        self._fullnames[-1] = self._fullnames[-1][:-1] # strip last comma

    def _getStepStatus(self, botmaster, builderName, stepName):
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
        current = builder.builder_status.getCurrentBuilds()

        if not current:
            msg = "no builds building in builder %r" % builderName
            if self.idlePolicy == "error":
                raise BadStepError(msg)
            elif self.idlePolicy == "ignore":
                # don't hang around waiting (assume the build has finished)
                log.msg("Blocker: " + msg + ": skipping it")
                return None
            elif self.idlePolicy == "block":
                raise RuntimeError("not implemented yet")

        # XXX what if there is more than one build a-building?
        build_status = current[0]
        log.msg("Blocker.start: found builder=%r, build_status=%r" % (builder, build_status))

        index = None
        for step_status in build_status.getSteps():
            if step_status.name == stepName:
                return step_status
        raise BadStepError(
            "builder %r has no step named %r" % (builderName, stepName))

    def start(self):
        log.msg("Blocker.start: searching for steps %s" % "".join(self._fullnames))
        self.step_status.setText(["blocking on"] + self._fullnames)

        botmaster = self.build.slavebuilder.slave.parent
        stepStatusList = []             # list of BuildStepStatus objects
        errors = []                     # list of strings
        for (builderName, stepName) in self.upstreamSteps:
            try:
                stepStatus = self._getStepStatus(botmaster, builderName, stepName)
            except BadStepError, err:
                errors.append(err.message)
            else:
                if stepStatus is not None:
                    stepStatusList.append(stepStatus)

        if len(errors) == 1:
            raise BadStepError(errors[0])
        elif len(errors) > 1:
            raise BadStepError("multiple errors:\n" + "\n".join(errors))

        deferreds = []
        for stepStatus in stepStatusList:
            deferreds.append(stepStatus.waitUntilFinished())

        # N.B. DeferredList has nifty options that we could use here:
        #  - fireOnOneCallback=True would mean "block until *any* upstream step
        #    completes", i.e. changes Blocker from "and" to "or" semantics
        #  - fireOnOneErrback=True would let us fail early if any of the upstream
        #    steps errback (i.e. throw an exception -- not for build failure)
        deferredList = defer.DeferredList(deferreds)
        deferredList.addCallback(self.finished)

    def finished(self, resultList):
        from buildbot.status import builder

        log.msg("Blocker.finished: resultList=%r" % resultList)
        overallCode = builder.SUCCESS
        overallText = []

        # Compute an overall status code.  This is rather arbitrary but
        # it seems to work: if all upstream steps succeeded, the Blocker
        # succeeds; otherwise, the status of the blocker is the status
        # of the first non-SUCCESS upstream step.
        for (success, results) in resultList:
            # 'success' here is in the Deferred sense, not the Buildbot
            # sense: ie. it's only False if the upstream BuildStep threw
            # an exception
            if not success:
                overallCode = builder.EXCEPTION
                overallText.append("exception")
            else:
                (code, text) = results.getResults()
                log.msg("Blocker.finished: results=%r, code=%r, text=%r, overallCode=%r"
                        % (results, code, text, overallCode))

                if code != builder.SUCCESS and overallCode == builder.SUCCESS:
                    overallCode = code
                overallText.extend(text)

        log.msg("Blocker.finished: overallCode=%r, overallText=%r"
                % (overallCode, overallText))

        fullnames = self._fullnames[:]
        fullnames[-1] += ":"
        self.step_status.setText(fullnames + [builder.Results[overallCode]])
        BuildStep.finished(self, (overallCode, overallText))
