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

        # "full names" of the upstream steps (for status reporting)
        self._fullnames = ["%s.%s" % step for step in self.upstreamSteps]

    def _getStepStatus(self, botmaster, builderName, stepName):
        try:
            builder = botmaster.builders[builderName]
        except KeyError:
            raise BadStepError(
                "no builder named %r" % builderName)
        if not builder.building:
            raise BadStepError(
                "no builds building in builder %r" % builderName)

        # XXX what if there is more than one build a-building?
        build = builder.building[0]
        log.msg("Blocker.start: found builder=%r, build=%r" % (builder, build))

        index = None
        for (idx, factory) in enumerate(build.stepFactories):
            name = factory[1].get('name') # not all steps have a name!
            if name is not None and name == stepName:
                index = idx
                break
        if index is None:
            raise BadStepError(
                "builder %r has no step named %r" % (builderName, stepName))
        log.msg("Blocker.start: step %r is at index %d"
                % (stepName, index))

        return build.build_status.steps[index]

    def start(self):
        log.msg("Blocker.start: searching for steps %r" % self._fullnames)
        self.step_status.setText(["blocking on"] + self._fullnames)

        botmaster = self.build.slavebuilder.slave.parent
        stepStatusList = []             # list of BuildStepStatus objects
        errors = []                     # list of strings
        for (builderName, stepName) in self.upstreamSteps:
            try:
                stepStatusList.append(
                    self._getStepStatus(botmaster, builderName, stepName))
            except BadStepError, err:
                errors.append(err.message)
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

        self.step_status.setText(self._fullnames + [builder.Results[overallCode]])
        BuildStep.finished(self, (overallCode, overallText))
