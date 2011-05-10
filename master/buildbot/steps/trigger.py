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

from buildbot.process.buildstep import LoggingBuildStep, SUCCESS, FAILURE, EXCEPTION
from buildbot.process.properties import Properties
from buildbot.schedulers.triggerable import Triggerable
from twisted.python import log
from twisted.internet import defer

class Trigger(LoggingBuildStep):
    """I trigger a scheduler.Triggerable, to use one or more Builders as if
    they were a single buildstep (like a subroutine call).
    """
    name = "trigger"

    flunkOnFailure = True

    def __init__(self, schedulerNames=[], sourceStamp=None, updateSourceStamp=None, alwaysUseLatest=False,
                 waitForFinish=False, set_properties={}, copy_properties=[], **kwargs):
        """
        Trigger the given schedulers when this step is executed.

        @param schedulerNames: A list of scheduler names that should be
                               triggered. Schedulers can be specified using
                               WithProperties, if desired.

        @param sourceStamp: A dict containing the source stamp to use for the
                            build. Keys must include branch, revision, repository and
                            project. In addition, patch_body, patch_level, and
                            patch_subdir can be specified. Only one of
                            sourceStamp, updateSourceStamp and alwaysUseLatest
                            can be specified. Any of these can be specified using
                            WithProperties, if desired.

        @param updateSourceStamp: If True (the default), I will try to give
                                  the schedulers an absolute SourceStamp for
                                  their builds, so that a HEAD build will use
                                  the same revision even if more changes have
                                  occurred since my build's update step was
                                  run. If False, I will use the original
                                  SourceStamp unmodified.

        @param alwaysUseLatest: If False (the default), I will give the
                                SourceStamp of the current build to the
                                schedulers (as controled by updateSourceStamp).
                                If True, I will give the schedulers  an empty
                                SourceStamp, corresponding to the latest
                                revision.

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
        if sourceStamp and updateSourceStamp:
            raise ValueError("You can't specify both sourceStamp and updateSourceStamp")
        if sourceStamp and alwaysUseLatest:
            raise ValueError("You can't specify both sourceStamp and alwaysUseLatest")
        if alwaysUseLatest and updateSourceStamp:
            raise ValueError("You can't specify both alwaysUseLatest and updateSourceStamp")
        self.schedulerNames = schedulerNames
        self.sourceStamp = sourceStamp
        self.updateSourceStamp = updateSourceStamp or not (alwaysUseLatest or sourceStamp)
        self.alwaysUseLatest = alwaysUseLatest
        self.waitForFinish = waitForFinish
        self.set_properties = set_properties
        self.copy_properties = copy_properties
        self.running = False
        self.ended = False
        LoggingBuildStep.__init__(self, **kwargs)
        self.addFactoryArguments(schedulerNames=schedulerNames,
                                 sourceStamp=sourceStamp,
                                 updateSourceStamp=updateSourceStamp,
                                 alwaysUseLatest=alwaysUseLatest,
                                 waitForFinish=waitForFinish,
                                 set_properties=set_properties,
                                 copy_properties=copy_properties)

    def interrupt(self, reason):
        if self.running:
            self.step_status.setText(["interrupted"])
            return self.end(EXCEPTION)

    def end(self, result):
        if not self.ended:
            self.ended = True
            return self.finished(result)

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

        # (is there an easier way to find the BuildMaster?)
        all_schedulers = self.build.builder.botmaster.parent.allSchedulers()
        all_schedulers = dict([(sch.name, sch) for sch in all_schedulers])
        unknown_schedulers = []
        triggered_schedulers = []

        # TODO: don't fire any schedulers if we discover an unknown one
        for scheduler in self.schedulerNames:
            scheduler = properties.render(scheduler)
            if all_schedulers.has_key(scheduler):
                sch = all_schedulers[scheduler]
                if isinstance(sch, Triggerable):
                    triggered_schedulers.append(scheduler)
                else:
                    unknown_schedulers.append(scheduler)
            else:
                unknown_schedulers.append(scheduler)

        if unknown_schedulers:
            self.step_status.setText(['no scheduler:'] + unknown_schedulers)
            return self.end(FAILURE)

        master = self.build.builder.botmaster.parent # seriously?!
        if self.sourceStamp:
            d = master.db.sourcestamps.addSourceStamp(**properties.render(self.sourceStamp))
        elif self.alwaysUseLatest:
            d = defer.succeed(None)
        else:
            ss = self.build.getSourceStamp()
            if self.updateSourceStamp:
                got = properties.getProperty('got_revision')
                if got:
                    ss = ss.getAbsoluteSourceStamp(got)
            d = ss.getSourceStampId(master)
        def start_builds(ssid):
            dl = []
            for scheduler in triggered_schedulers:
                sch = all_schedulers[scheduler]
                dl.append(sch.trigger(ssid, set_props=props_to_set))
            self.step_status.setText(['triggered'] + triggered_schedulers)

            d = defer.DeferredList(dl, consumeErrors=1)
            if self.waitForFinish:
                return d
            else:
                # do something to handle errors
                d.addErrback(log.err,
                        '(ignored) while invoking Triggerable schedulers:')
                self.end(SUCCESS)
                return None
        d.addCallback(start_builds)

        def cb(rclist):
            rc = SUCCESS # (this rc is not the same variable as that above)
            for was_cb, results in rclist:
                # TODO: make this algo more configurable
                if not was_cb:
                    rc = EXCEPTION
                    log.err(results)
                    break
                if results == FAILURE:
                    rc = FAILURE
            return self.end(rc)
        def eb(why):
            return self.end(FAILURE)

        if self.waitForFinish:
            d.addCallbacks(cb, eb)

        d.addErrback(log.err, '(ignored) while triggering builds:')
