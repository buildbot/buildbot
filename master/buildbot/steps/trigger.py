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

from buildbot import config
from buildbot.interfaces import ITriggerableScheduler
from buildbot.process.buildstep import BuildStep
from buildbot.process.buildstep import CANCELLED
from buildbot.process.buildstep import EXCEPTION
from buildbot.process.buildstep import SUCCESS
from buildbot.process.properties import Properties
from buildbot.process.properties import Property
from buildbot.status.results import statusToString
from buildbot.status.results import worst_status
from twisted.internet import defer
from twisted.python import log


class Trigger(BuildStep):
    name = "trigger"

    renderables = ['set_properties', 'schedulerNames', 'sourceStamps',
                   'updateSourceStamp', 'alwaysUseLatest', 'parent_relationship']

    flunkOnFailure = True

    def __init__(self, schedulerNames=[], sourceStamp=None, sourceStamps=None,
                 updateSourceStamp=None, alwaysUseLatest=False,
                 waitForFinish=False, set_properties={},
                 copy_properties=[], parent_relationship="triggered from", **kwargs):
        if not schedulerNames:
            config.error(
                "You must specify a scheduler to trigger")
        if (sourceStamp or sourceStamps) and (updateSourceStamp is not None):
            config.error(
                "You can't specify both sourceStamps and updateSourceStamp")
        if (sourceStamp or sourceStamps) and alwaysUseLatest:
            config.error(
                "You can't specify both sourceStamps and alwaysUseLatest")
        if alwaysUseLatest and (updateSourceStamp is not None):
            config.error(
                "You can't specify both alwaysUseLatest and updateSourceStamp"
            )
        self.schedulerNames = schedulerNames
        self.sourceStamps = sourceStamps or []
        if sourceStamp:
            self.sourceStamps.append(sourceStamp)
        if updateSourceStamp is not None:
            self.updateSourceStamp = updateSourceStamp
        else:
            self.updateSourceStamp = not (alwaysUseLatest or self.sourceStamps)
        self.alwaysUseLatest = alwaysUseLatest
        self.waitForFinish = waitForFinish
        properties = {}
        properties.update(set_properties)
        for i in copy_properties:
            properties[i] = Property(i)
        self.set_properties = properties
        self.parent_relationship = parent_relationship
        self.running = False
        self.ended = False
        self.brids = []
        BuildStep.__init__(self, **kwargs)

    def interrupt(self, reason):
        # FIXME: new style step cannot be interrupted anymore by just calling finished()
        #        (which was a bad idea in the first place)
        # we should claim the self.brids, and CANCELLED them
        # if they were already claimed, stop the associated builds via data api
        # then the big deferredlist will automatically be called
        if self.running and not self.ended:
            self.setStateStrings(["interrupted"])
            self.ended = True

    # Create the properties that are used for the trigger
    def createTriggerProperties(self):
        # make a new properties object from a dict rendered by the old
        # properties object
        trigger_properties = Properties()
        trigger_properties.update(self.set_properties, "Trigger")
        return trigger_properties

    # Get all scheduler instances that were configured
    # A tuple of (triggerables, invalidnames) is returned
    def getSchedulers(self):
        all_schedulers = self.build.builder.botmaster.parent.allSchedulers()
        all_schedulers = dict([(sch.name, sch) for sch in all_schedulers])
        invalid_schedulers = []
        triggered_schedulers = []
        # don't fire any schedulers if we discover an unknown one
        for scheduler in self.schedulerNames:
            scheduler = scheduler
            if scheduler in all_schedulers:
                sch = all_schedulers[scheduler]
                if ITriggerableScheduler.providedBy(sch):
                    triggered_schedulers.append(sch)
                else:
                    invalid_schedulers.append(scheduler)
            else:
                invalid_schedulers.append(scheduler)

        return (triggered_schedulers, invalid_schedulers)

    def prepareSourcestampListForTrigger(self):
        if self.sourceStamps:
            ss_for_trigger = {}
            for ss in self.sourceStamps:
                codebase = ss.get('codebase', '')
                assert codebase not in ss_for_trigger, "codebase specified multiple times"
                ss_for_trigger[codebase] = ss
            return ss_for_trigger.values()

        if self.alwaysUseLatest:
            return []

        # start with the sourcestamps from current build
        ss_for_trigger = {}
        objs_from_build = self.build.getAllSourceStamps()
        for ss in objs_from_build:
            ss_for_trigger[ss.codebase] = ss.asDict()

        # overrule revision in sourcestamps with got revision
        if self.updateSourceStamp:
            got = self.build.build_status.getAllGotRevisions()
            for codebase in ss_for_trigger:
                if codebase in got:
                    ss_for_trigger[codebase]['revision'] = got[codebase]

        return ss_for_trigger.values()

    @defer.inlineCallbacks
    def worstStatus(self, overall_results, rclist):
        for was_cb, results in rclist:
            if isinstance(results, tuple):
                results, _ = results

            if not was_cb:
                yield self.addLogWithFailure(results)
                results = EXCEPTION
            overall_results = worst_status(overall_results, results)
        defer.returnValue(overall_results)

    @defer.inlineCallbacks
    def addBuildUrls(self, rclist):
        for was_cb, results in rclist:
            if isinstance(results, tuple):
                results, brids = results

            if was_cb:  # errors were already logged in worstStatus
                for buildername, br in brids.iteritems():
                    builds = yield self.master.db.builds.getBuilds(buildrequestid=br)
                    for build in builds:
                        num = build['number']
                        url = self.master.status.getURLForBuild(buildername, num)
                        yield self.step_status.addURL("%s: %s #%d" % (statusToString(results),
                                                                      buildername, num), url)

    @defer.inlineCallbacks
    def run(self):
        # Get all triggerable schedulers and check if there are invalid schedules
        (triggered_schedulers, invalid_schedulers) = self.getSchedulers()
        if invalid_schedulers:
            yield self.setStateStrings(['not valid scheduler:'] + invalid_schedulers)
            defer.returnValue(EXCEPTION)

        self.running = True

        props_to_set = self.createTriggerProperties()

        ss_for_trigger = self.prepareSourcestampListForTrigger()

        dl = []
        triggered_names = []
        results = SUCCESS
        for sch in triggered_schedulers:
            idsDeferred, resultsDeferred = sch.trigger(
                waited_for=self.waitForFinish, sourcestamps=ss_for_trigger,
                set_props=props_to_set,
                parent_buildid=self.build.buildid,
                parent_relationship=self.parent_relationship
            )
            # we are not in a hurry of starting all in parallel and managing
            # the deferred lists, just let the db writes be serial.
            try:
                bsid, brids = yield idsDeferred
            except Exception, e:
                yield self.addLogWithException(e)
                results = EXCEPTION

            self.brids.extend(brids.values())
            for brid in brids.values():
                # put the url to the brids, so that we can have the status from the beginning
                url = self.master.status.getURLForBuildrequest(brid)
                yield self.addURL("%s #%d" % (sch.name, brid), url)
            dl.append(resultsDeferred)
            triggered_names.append(sch.name)
            if self.ended:
                defer.returnValue(CANCELLED)
        yield self.setStateStrings(['triggered'] + triggered_names)

        if self.waitForFinish:
            rclist = yield defer.DeferredList(dl, consumeErrors=1)
            # we were interrupted, don't bother update status
            if self.ended:
                defer.returnValue(CANCELLED)
            yield self.addBuildUrls(rclist)
            results = yield self.worstStatus(results, rclist)
        else:
            # do something to handle errors
            for d in dl:
                d.addErrback(log.err,
                             '(ignored) while invoking Triggerable schedulers:')

        defer.returnValue(results)
