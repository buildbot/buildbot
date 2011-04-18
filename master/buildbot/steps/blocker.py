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

from twisted.python import log, failure
from twisted.internet import reactor

from buildbot.process.buildstep import BuildStep
from buildbot.status import builder, buildstep

class BadStepError(Exception):
    """Raised by Blocker when it is passed an upstream step that cannot
    be found or is in a bad state."""
    pass

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
    idlePolicy = "block"
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

        # list of build steps (as BuildStepStatus objects) that we're
        # currently waiting on
        self._blocking_steps = []

        # set of builders (as BuilderStatus objects) that have to start
        # a Build before we can block on one of their BuildSteps
        self._blocking_builders = set()

        self._overall_code = builder.SUCCESS # assume the best
        self._overall_text = []

        self._timer = None              # object returned by reactor.callLater()
        self._timed_out = False

    def __str__(self):
        return self.name

    def __repr__(self):
        return "<%s %x: %s>" % (self.__class__.__name__, id(self), self.name)

    def _log(self, message, *args):
        log.msg(repr(self) + ": " + (message % args))

    def buildsMatch(self, buildStatus1, buildStatus2):
        """
        Return true if buildStatus1 and buildStatus2 are from related
        builds, i.e. a Blocker step running in buildStatus2 should be
        blocked by an upstream step in buildStatus1.  Return false if
        they are unrelated.

        Default implementation simply raises NotImplementedError: you
        *must* subclass Blocker and implement this method, because
        BuildBot currently provides no way to relate different builders.
        This might change if ticket #875 (\"build flocks\") is
        implemented.
        """
        raise NotImplementedError(
            "abstract method: you must subclass Blocker "
            "and implement buildsMatch()")

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
        myBuildStatus = self.build.getStatus()
        builderStatus = builder.builder_status
        matchingBuild = None

        # Get a list of all builds in this builder, past and present.
        # This is subtly broken because BuilderStatus does not expose
        # the information we need; in fact, it doesn't even necessarily
        # *have* that information. The contents of the build cache can
        # change unpredictably if someone happens to view the waterfall
        # at an inopportune moment: yikes! The right fix is to keep old
        # builds in the database and for BuilderStatus to expose the
        # needed information. When that is implemented, then Blocker
        # needs to be adapted to use it, and *then* Blocker should be
        # safe to use.
        all_builds = (builderStatus.buildCache.values() +
                      builderStatus.getCurrentBuilds())

        for buildStatus in all_builds:
            if self.buildsMatch(myBuildStatus, buildStatus):
                matchingBuild = buildStatus
                break

        if matchingBuild is None:
            msg = "no matching builds found in builder %r" % builderName
            if self.idlePolicy == "error":
                raise BadStepError(msg + " (is it idle?)")
            elif self.idlePolicy == "ignore":
                # don't hang around waiting (assume the build has finished)
                self._log(msg + ": skipping it")
                return None
            elif self.idlePolicy == "block":
                self._log(msg + ": will block until it starts a build")
                self._blocking_builders.add(builderStatus)
                return None

        self._log("found builder %r: %r", builderName, builder)
        return matchingBuild

    def _getStepStatus(self, buildStatus, stepName):
        for step_status in buildStatus.getSteps():
            if step_status.name == stepName:
                self._log("found build step %r in builder %r: %r",
                          stepName, buildStatus.getBuilder().getName(), step_status)
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
        self.step_status.setText(self._getBlockingStatusText())

        if self.timeout is not None:
            self._timer = reactor.callLater(self.timeout, self._timeoutExpired)

        self._log("searching for upstream build steps")
        botmaster = self.build.slavebuilder.slave.parent
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
                self._blocking_steps.append(stepStatus)

        if len(errors) == 1:
            raise BadStepError(errors[0])
        elif len(errors) > 1:
            raise BadStepError("multiple errors:\n" + "\n".join(errors))

        self._log("will block on %d upstream build steps: %r",
                  len(self._blocking_steps), self._blocking_steps)
        if self._blocking_builders:
            self._log("will also block on %d builders starting a build: %r",
                      len(self._blocking_builders), self._blocking_builders)

        # Now we can register with each blocking step (BuildStepStatus
        # objects, actually) that we want a callback when the step
        # finishes.  Need to iterate over a copy of _blocking_steps
        # because it can be modified while we iterate: if any upstream
        # step is already finished, the _upstreamStepFinished() callback
        # will be called immediately.
        for stepStatus in self._blocking_steps[:]:
            self._awaitStepFinished(stepStatus)
        self._log("after registering for each upstream build step, "
                  "_blocking_steps = %r",
                  self._blocking_steps)

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
        # Hmmm: this step has failed.  But it is still subscribed to
        # various upstream events, so if they happen despite this
        # timeout, various callbacks in this object will still be
        # called.  This could be confusing and is definitely a bit
        # untidy: probably we should unsubscribe from all those various
        # events.  Even better if we had a test case to ensure that we
        # really do.
        self._log("timeout (%.1f sec) expired", self.timeout)
        self.step_status.setColor("red")
        self.step_status.setText(self._getTimeoutStatusText())
        self.finished(builder.FAILURE)
        self._timed_out = True

    def _upstreamStepFinished(self, stepStatus):
        assert isinstance(stepStatus, buildstep.BuildStepStatus)
        self._log("upstream build step %s:%s finished; results=%r",
                  stepStatus.getBuild().builder.getName(),
                  stepStatus.getName(),
                  stepStatus.getResults())

        if self._timed_out:
            # don't care about upstream steps: just clean up and get out
            self._blocking_steps.remove(stepStatus)
            return

        (code, text) = stepStatus.getResults()
        if code != builder.SUCCESS and self._overall_code == builder.SUCCESS:
            # first non-SUCCESS result wins
            self._overall_code = code
        self._overall_text.extend(text)
        self._log("now _overall_code=%r, _overall_text=%r",
                  self._overall_code, self._overall_text)

        self._blocking_steps.remove(stepStatus)
        self._checkFinished()

    def _upstreamBuildStarted(self, builderStatus, buildStatus, receiver):
        assert isinstance(builderStatus, builder.BuilderStatus)
        self._log("builder %r (%r) started a build; buildStatus=%r",
                  builderStatus, builderStatus.getName(), buildStatus)

        myBuildStatus = self.build.getStatus()
        if not self.buildsMatch(myBuildStatus, buildStatus):
            self._log("but the just-started build does not match: "
                      "ignoring it")
            return

        builderStatus.unsubscribe(receiver)

        # Need to accumulate newly-discovered steps separately, so we
        # can add them to _blocking_steps en masse before subscribing to
        # their "finish" events.
        new_blocking_steps = []
        for (builderName, stepName) in self.upstreamSteps:
            if builderName == builderStatus.getName():
                try:
                    stepStatus = self._getStepStatus(buildStatus, stepName)
                except BadStepError:
                    self.failed(failure.Failure())
                    #log.err()
                    #self._overall_code = builder.EXCEPTION
                    #self._overall_text.append(str(err))
                else:
                    new_blocking_steps.append(stepStatus)

        self._blocking_steps.extend(new_blocking_steps)
        for stepStatus in new_blocking_steps:
            self._awaitStepFinished(stepStatus)

        self._blocking_builders.remove(builderStatus)
        self._checkFinished()

    def _checkFinished(self):
        if self.step_status.isFinished():
            # this can happen if _upstreamBuildStarted() catches BadStepError
            # and fails the step
            self._log("_checkFinished: already finished, so nothing to do here")
            return

        self._log("_checkFinished: _blocking_steps=%r, _blocking_builders=%r",
                  self._blocking_steps, self._blocking_builders)

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
        self.blocker._upstreamBuildStarted(self.builderStatus, buildStatus, self)

    def buildFinished(self, *args):
        pass
