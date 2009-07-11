from buildbot.process.buildstep import LoggingBuildStep, SUCCESS, FAILURE, EXCEPTION
from buildbot.process.properties import Properties
from buildbot.scheduler import Triggerable
from twisted.internet import defer

class Trigger(LoggingBuildStep):
    """I trigger a scheduler.Triggerable, to use one or more Builders as if
    they were a single buildstep (like a subroutine call).
    """
    name = "trigger"

    flunkOnFailure = True

    def __init__(self, schedulerNames=[], updateSourceStamp=True,
                 waitForFinish=False, set_properties={}, copy_properties=[], **kwargs):
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

        @param set_properties: A dictionary of properties to set for any
                               builds resulting from this trigger.  These
                               properties will override properties set in the
                               Triggered scheduler's constructor.

        @param copy_properties: a list of property names to copy verbatim
                                into any builds resulting from this trigger.

        """
        assert schedulerNames, "You must specify a scheduler to trigger"
        self.schedulerNames = schedulerNames
        self.updateSourceStamp = updateSourceStamp
        self.waitForFinish = waitForFinish
        self.set_properties = set_properties
        self.copy_properties = copy_properties
        self.running = False
        LoggingBuildStep.__init__(self, **kwargs)
        self.addFactoryArguments(schedulerNames=schedulerNames,
                                 updateSourceStamp=updateSourceStamp,
                                 waitForFinish=waitForFinish,
                                 set_properties=set_properties,
                                 copy_properties=copy_properties)

    def interrupt(self, reason):
        # TODO: this doesn't actually do anything.
        if self.running:
            self.step_status.setText(["interrupted"])

    def start(self):
        properties = self.build.getProperties()

        # make a new properties object from a dict rendered by the old 
        # properties object
        props_to_set = Properties()
        props_to_set.update(properties.render(self.set_properties), "Trigger")
        for p in self.copy_properties:
            if p not in properties:
                raise RuntimeError("copy_property '%s' is not set in the triggering build" % p)
            props_to_set.setProperty(p, properties[p],
                        "%s (in triggering build)" % properties.getPropertySource(p))

        self.running = True
        ss = self.build.getSourceStamp()
        if self.updateSourceStamp:
            got = properties.getProperty('got_revision')
            if got:
                ss = ss.getAbsoluteSourceStamp(got)

        # (is there an easier way to find the BuildMaster?)
        all_schedulers = self.build.builder.botmaster.parent.allSchedulers()
        all_schedulers = dict([(sch.name, sch) for sch in all_schedulers])
        unknown_schedulers = []
        triggered_schedulers = []

        # TODO: don't fire any schedulers if we discover an unknown one
        dl = []
        for scheduler in self.schedulerNames:
            scheduler = properties.render(scheduler)
            if all_schedulers.has_key(scheduler):
                sch = all_schedulers[scheduler]
                if isinstance(sch, Triggerable):
                    dl.append(sch.trigger(ss, set_props=props_to_set))
                    triggered_schedulers.append(scheduler)
                else:
                    unknown_schedulers.append(scheduler)
            else:
                unknown_schedulers.append(scheduler)

        if unknown_schedulers:
            self.step_status.setText(['no scheduler:'] + unknown_schedulers)
            rc = FAILURE
        else:
            rc = SUCCESS
            self.step_status.setText(['triggered'] + triggered_schedulers)

        if self.waitForFinish:
            d = defer.DeferredList(dl, consumeErrors=1)
        else:
            d = defer.succeed([])

        def cb(rclist):
            rc = SUCCESS # (this rc is not the same variable as that above)
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
