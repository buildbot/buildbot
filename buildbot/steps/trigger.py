from buildbot.process.buildstep import LoggingBuildStep, SUCCESS, FAILURE, EXCEPTION
from buildbot.steps.shell import WithProperties
from buildbot.scheduler import Triggerable
from twisted.internet import defer

class Trigger(LoggingBuildStep):
    """I trigger a scheduler.Triggerable, to use one or more Builders as if
    they were a single buildstep (like a subroutine call).
    """
    name = "trigger"

    flunkOnFailure = True

    def __init__(self, schedulerNames=[], updateSourceStamp=True,
                 waitForFinish=False, **kwargs):
        """
        Trigger the given schedulers when this step is executed.

        @param schedulerNames: A list of scheduler names that should be
                               triggered. Schedulers can be specified using
                               WithProperties, if desired.

        @param updateSourceStamp: If True (the default), I will try to give
                                  the schedulers an absolute SourceStamp for
                                  their builds, so that a HEAD build will use
                                  the same revision even if more changes have
                                  occurred since my build's update step was
                                  run. If False, I will use the original
                                  SourceStamp unmodified.

        @param waitForFinish: If False (the default), this step will finish
                              as soon as I've started the triggered
                              schedulers. If True, I will wait until all of
                              the triggered schedulers have finished their
                              builds.
        """
        assert schedulerNames, "You must specify a scheduler to trigger"
        self.schedulerNames = schedulerNames
        self.updateSourceStamp = updateSourceStamp
        self.waitForFinish = waitForFinish
        self.running = False
        LoggingBuildStep.__init__(self, **kwargs)
        self.addFactoryArguments(schedulerNames=schedulerNames,
                                 updateSourceStamp=updateSourceStamp,
                                 waitForFinish=waitForFinish)

    def interrupt(self, reason):
        # TODO: this doesn't actually do anything.
        if self.running:
            self.step_status.setColor("red")
            self.step_status.setText(["interrupted"])

    def start(self):
        custom_props = {}
        self.running = True
        ss = self.build.getSourceStamp()
        if self.updateSourceStamp:
            got = None
            try:
                got = self.build.getProperty('got_revision')
            except KeyError:
                pass
            if got:
                ss = ss.getAbsoluteSourceStamp(got)
        custom_props = self.build.getCustomProperties()
        # (is there an easier way to find the BuildMaster?)
        all_schedulers = self.build.builder.botmaster.parent.allSchedulers()
        all_schedulers = dict([(sch.name, sch) for sch in all_schedulers])
        unknown_schedulers = []
        triggered_schedulers = []

        # TODO: don't fire any schedulers if we discover an unknown one
        dl = []
        for scheduler in self.schedulerNames:
            if isinstance(scheduler, WithProperties):
                scheduler = scheduler.render(self.build)
            if all_schedulers.has_key(scheduler):
                sch = all_schedulers[scheduler]
                if isinstance(sch, Triggerable):
                    dl.append(sch.trigger(ss, custom_props))
                    triggered_schedulers.append(scheduler)
                else:
                    unknown_schedulers.append(scheduler)
            else:
                unknown_schedulers.append(scheduler)

        if unknown_schedulers:
            self.step_status.setColor("red")
            self.step_status.setText(['no scheduler:'] + unknown_schedulers)
            rc = FAILURE
        else:
            rc = SUCCESS
            self.step_status.setText(['triggered'] + triggered_schedulers)
            if self.waitForFinish:
                self.step_status.setColor("yellow")
            else:
                self.step_status.setColor("green")

        if self.waitForFinish:
            d = defer.DeferredList(dl, consumeErrors=1)
        else:
            d = defer.succeed([])

        # TODO: review this shadowed 'rc' value: can the callback modify the
        # one that was defined above?
        def cb(rclist):
            rc = SUCCESS
            for was_cb, buildsetstatus in rclist:
                # TODO: make this algo more configurable
                if not was_cb:
                    rc = EXCEPTION
                    break
                if buildsetstatus.getResults() == FAILURE:
                    rc = FAILURE
            return self.finished(rc)

        def eb(why):
            return self.finished(FAILURE)

        d.addCallbacks(cb, eb)
