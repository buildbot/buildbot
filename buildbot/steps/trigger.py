from buildbot.process.buildstep import LoggingBuildStep, SUCCESS, FAILURE, EXCEPTION
from buildbot.steps.shell import WithProperties
from buildbot.scheduler import Triggerable
from twisted.internet import defer

class Trigger(LoggingBuildStep):
    """
    I trigger a Triggerable.  It's fun.
    """
    name = "trigger"

    flunkOnFailure = True

    def __init__(self,
        schedulers=[],
        updateSourceStamp=False,
        waitForFinish=False,
        **kwargs):
        """
        Trigger the given schedulers when this step is executed.

        @var schedulers: list of schedulers' names that should be triggered.  Schedulers
        can be specified using WithProperties, if desired.

        @var updateSourceStamp: should I update the source stamp to
        an absolute SourceStamp before triggering a new build?

        @var waitForFinish: should I wait for all of the triggered schedulers to finish
        their builds?
        """
        assert schedulers, "You must specify a scheduler to trigger"
        self.schedulers = schedulers
        self.updateSourceStamp = updateSourceStamp
        self.waitForFinish = waitForFinish
        self.running = False
        LoggingBuildStep.__init__(self, **kwargs)
        self.addFactoryArguments(schedulers=schedulers,
                                 updateSourceStamp=updateSourceStamp,
                                 waitForFinish=waitForFinish)

    def interrupt(self, reason):
        if self.running:
            self.step_status.setColor("red")
            self.step_status.setText(["interrupted"])

    def start(self):
        self.running = True
        ss = self.build.getSourceStamp()
        if self.updateSourceStamp:
            ss = ss.getAbsoluteSourceStamp(self.build.getProperty('got_revision'))
        # (is there an easier way to find the BuildMaster?)
        all_schedulers = self.build.builder.botmaster.parent.allSchedulers()
        all_schedulers = dict([(sch.name, sch) for sch in all_schedulers])
        unknown_schedulers = []
        triggered_schedulers = []

        dl = []
        for scheduler in self.schedulers:
            if isinstance(scheduler, WithProperties):
                scheduler = scheduler.render(self.build)
            if all_schedulers.has_key(scheduler):
                sch = all_schedulers[scheduler]
                if isinstance(sch, Triggerable):
                    dl.append(sch.trigger(ss))
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
