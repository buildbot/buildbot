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
    name = "trigger"

    renderables = [ 'set_properties', 'schedulerNames', 'sourceStamp',
                    'updateSourceStamp', 'alwaysUseLatest' ]

    flunkOnFailure = True

    def __init__(self, schedulerNames=[], sourceStamp=None, updateSourceStamp=None, alwaysUseLatest=False,
                 waitForFinish=False, set_properties={}, copy_properties=[], **kwargs):
        if not schedulerNames:
            raise ValueError("You must specify a scheduler to trigger")
        if sourceStamp and (updateSourceStamp is not None):
            raise ValueError("You can't specify both sourceStamp and updateSourceStamp")
        if sourceStamp and alwaysUseLatest:
            raise ValueError("You can't specify both sourceStamp and alwaysUseLatest")
        if alwaysUseLatest and (updateSourceStamp is not None):
            raise ValueError("You can't specify both alwaysUseLatest and updateSourceStamp")
        self.schedulerNames = schedulerNames
        self.sourceStamp = sourceStamp
        if updateSourceStamp is not None:
            self.updateSourceStamp = updateSourceStamp
        else:
            self.updateSourceStamp = not (alwaysUseLatest or sourceStamp)
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
        if self.running and not self.ended:
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
        props_to_set.update(self.set_properties, "Trigger")
        for p in self.copy_properties:
            if p not in properties:
                continue
            props_to_set.setProperty(p, properties[p],
                        "%s (in triggering build)" % properties.getPropertySource(p))

        self.running = True

        # (is there an easier way to find the BuildMaster?)
        all_schedulers = self.build.builder.botmaster.parent.allSchedulers()
        all_schedulers = dict([(sch.name, sch) for sch in all_schedulers])
        unknown_schedulers = []
        triggered_schedulers = []

        # don't fire any schedulers if we discover an unknown one
        for scheduler in self.schedulerNames:
            scheduler = scheduler
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
            d = master.db.sourcestamps.addSourceStamp(**self.sourceStamp)
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

            if self.waitForFinish:
                return defer.DeferredList(dl, consumeErrors=1)
            else:
                # do something to handle errors
                for d in dl:
                    d.addErrback(log.err,
                        '(ignored) while invoking Triggerable schedulers:')
                self.end(SUCCESS)
                return None
        d.addCallback(start_builds)

        def cb(rclist):
            result = SUCCESS
            for was_cb, results in rclist:
                # TODO: make this algo more configurable
                if not was_cb:
                    result = EXCEPTION
                    log.err(results)
                    break
                if results == FAILURE:
                    result = FAILURE
            return self.end(result)
        def eb(why):
            return self.end(FAILURE)

        if self.waitForFinish:
            d.addCallbacks(cb, eb)

        d.addErrback(log.err, '(ignored) while triggering builds:')
