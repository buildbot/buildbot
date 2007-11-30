from twisted.python import log
from twisted.internet import defer
from buildbot.process.buildstep import BuildStep

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
        builder = botmaster.builders[builderName]
        assert builder.building, \
               "no builds building in builder %r" % builderName
        build = builder.building[0]   # buildbot.process.base.Build
        log.msg("Blocker.start: found builder=%r, build=%r"
                % (builder, build))

        #log.msg("Blocker.start: searching %d step factories for build step %r"
        #        % (len(build.stepFactories), stepName))
        index = None
        for (idx, factory) in enumerate(build.stepFactories):
            #log.msg("Blocker.start: idx=%d, factory=%r" % (idx, factory))
            name = factory[1].get('name') # not all steps have a name!
            if name is not None and name == stepName:
                index = idx
                break
        if index is None:
            raise RuntimeError("no step named %r found in builder %r"
                               % (stepName, builderName))
        log.msg("Blocker.start: step %r is at index %d"
                % (stepName, index))

        return build.build_status.steps[index]

    def start(self):
        log.msg("Blocker.start: searching for steps %r" % self._fullnames)
        self.step_status.setText(["blocking on"] + self._fullnames)

        botmaster = self.build.slavebuilder.slave.parent
        deferreds = []
        for (builderName, stepName) in self.upstreamSteps:
            stepStatus = self._getStepStatus(botmaster, builderName, stepName)
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
