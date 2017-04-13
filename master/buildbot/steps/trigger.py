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

from __future__ import absolute_import
from __future__ import print_function
from future.utils import iteritems
from future.utils import itervalues

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.interfaces import ITriggerableScheduler
from buildbot.process.buildstep import CANCELLED
from buildbot.process.buildstep import EXCEPTION
from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import BuildStep
from buildbot.process.properties import Properties
from buildbot.process.properties import Property
from buildbot.process.results import statusToString
from buildbot.process.results import worst_status


class Trigger(BuildStep):
    name = "trigger"

    renderables = [
        'alwaysUseLatest',
        'parent_relationship',
        'schedulerNames',
        'set_properties',
        'sourceStamps',
        'updateSourceStamp',
        'waitForFinish'
    ]

    flunkOnFailure = True

    def __init__(self, schedulerNames=None, sourceStamp=None, sourceStamps=None,
                 updateSourceStamp=None, alwaysUseLatest=False,
                 waitForFinish=False, set_properties=None,
                 copy_properties=None, parent_relationship="Triggered from",
                 unimportantSchedulerNames=None, **kwargs):
        if schedulerNames is None:
            schedulerNames = []
        if unimportantSchedulerNames is None:
            unimportantSchedulerNames = []
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
        if not set(schedulerNames).issuperset(set(unimportantSchedulerNames)):
            config.error(
                "unimportantSchedulerNames must be a subset of schedulerNames"
            )

        self.schedulerNames = schedulerNames
        self.unimportantSchedulerNames = unimportantSchedulerNames
        self.sourceStamps = sourceStamps or []
        if sourceStamp:
            self.sourceStamps.append(sourceStamp)
        if updateSourceStamp is not None:
            self.updateSourceStamp = updateSourceStamp
        else:
            self.updateSourceStamp = not (alwaysUseLatest or self.sourceStamps)
        self.alwaysUseLatest = alwaysUseLatest
        self.waitForFinish = waitForFinish

        if set_properties is None:
            set_properties = {}
        if copy_properties is None:
            copy_properties = []

        properties = {}
        properties.update(set_properties)
        for i in copy_properties:
            properties[i] = Property(i)
        self.set_properties = properties
        self.parent_relationship = parent_relationship
        self.running = False
        self.ended = False
        self.brids = []
        self.triggeredNames = None
        self.waitForFinishDeferred = None
        BuildStep.__init__(self, **kwargs)

    def interrupt(self, reason):
        # We cancel the buildrequests, as the data api handles
        # both cases:
        # - build started: stop is sent,
        # - build not created yet: related buildrequests are set to CANCELLED.
        # Note that there is an identified race condition though (more details
        # are available at buildbot.data.buildrequests).
        for brid in self.brids:
            self.master.data.control("cancel",
                                     {'reason':
                                         'parent build was interrupted'},
                                     ("buildrequests", brid))
        if self.running and not self.ended:
            self.ended = True
            # if we are interrupted because of a connection lost, we interrupt synchronously
            if self.build.conn is None and self.waitForFinishDeferred is not None:
                self.waitForFinishDeferred.cancel()

    # Create the properties that are used for the trigger
    def createTriggerProperties(self, properties):
        # make a new properties object from a dict rendered by the old
        # properties object
        trigger_properties = Properties()
        trigger_properties.update(properties, "Trigger")
        return trigger_properties

    def getSchedulerByName(self, name):
        # we use the fact that scheduler_manager is a multiservice, with schedulers as childs
        # this allow to quickly find schedulers instance by name
        schedulers = self.master.scheduler_manager.namedServices
        if name not in schedulers:
            raise ValueError("unknown triggered scheduler: %r" % (name,))
        sch = schedulers[name]
        if not ITriggerableScheduler.providedBy(sch):
            raise ValueError(
                "triggered scheduler is not ITriggerableScheduler: %r" % (name,))
        return sch

    # This customization endpoint allows users to dynamically select which
    # scheduler and properties to trigger
    def getSchedulersAndProperties(self):
        return [{
            'sched_name': sched,
            'props_to_set': self.set_properties,
            'unimportant': sched in self.unimportantSchedulerNames}
            for sched in self.schedulerNames]

    def prepareSourcestampListForTrigger(self):
        if self.sourceStamps:
            ss_for_trigger = {}
            for ss in self.sourceStamps:
                codebase = ss.get('codebase', '')
                assert codebase not in ss_for_trigger, "codebase specified multiple times"
                ss_for_trigger[codebase] = ss
            trigger_values = [ss_for_trigger[k] for k in sorted(ss_for_trigger.keys())]
            return trigger_values

        if self.alwaysUseLatest:
            return []

        # start with the sourcestamps from current build
        ss_for_trigger = {}
        objs_from_build = self.build.getAllSourceStamps()
        for ss in objs_from_build:
            ss_for_trigger[ss.codebase] = ss.asDict()

        # overrule revision in sourcestamps with got revision
        if self.updateSourceStamp:
            got = self.getAllGotRevisions()
            for codebase in ss_for_trigger:
                if codebase in got:
                    ss_for_trigger[codebase]['revision'] = got[codebase]

        trigger_values = [ss_for_trigger[k] for k in sorted(ss_for_trigger.keys())]
        return trigger_values

    def getAllGotRevisions(self):
        all_got_revisions = self.getProperty('got_revision', {})
        # For backwards compatibility all_got_revisions is a string if codebases
        # are not used. Convert to the default internal type (dict)
        if not isinstance(all_got_revisions, dict):
            all_got_revisions = {'': all_got_revisions}
        return all_got_revisions

    @defer.inlineCallbacks
    def worstStatus(self, overall_results, rclist, unimportant_brids):
        for was_cb, results in rclist:
            if isinstance(results, tuple):
                results, brids_dict = results

            if not was_cb:
                yield self.addLogWithFailure(results)
                results = EXCEPTION

            # brids_dict.values() represents the list of brids kicked by a certain scheduler.
            # We want to ignore the result of ANY brid that was kicked off
            # by an UNimportant scheduler.
            if set(unimportant_brids).issuperset(set(brids_dict.values())):
                continue
            overall_results = worst_status(overall_results, results)
        defer.returnValue(overall_results)

    @defer.inlineCallbacks
    def addBuildUrls(self, rclist):
        brids = {}
        for was_cb, results in rclist:
            if isinstance(results, tuple):
                results, brids = results
            builderNames = {}
            if was_cb:  # errors were already logged in worstStatus
                for builderid, br in iteritems(brids):
                    builds = yield self.master.db.builds.getBuilds(buildrequestid=br)
                    for build in builds:
                        builderid = build['builderid']
                        # When virtual builders are used, the builderid used for triggering
                        # is not the same as the one that the build actually got
                        if builderid not in builderNames:
                            builderDict = yield self.master.data.get(("builders", builderid))
                            builderNames[builderid] = builderDict["name"]
                        num = build['number']
                        url = self.master.status.getURLForBuild(builderid, num)
                        yield self.addURL("%s: %s #%d" % (statusToString(build["results"]),
                                                          builderNames[builderid], num), url)

    @defer.inlineCallbacks
    def run(self):
        schedulers_and_props = yield self.getSchedulersAndProperties()

        schedulers_and_props_list = []

        # To be back compatible we need to differ between old and new style
        # schedulers_and_props can either consist of 2 elements tuple or
        # dictionary
        for element in schedulers_and_props:
            if isinstance(element, dict):
                schedulers_and_props_list = schedulers_and_props
                break
            else:
                # Old-style back compatibility: Convert tuple to dict and make
                # it important
                d = {
                    'sched_name': element[0],
                    'props_to_set': element[1],
                    'unimportant': False
                }
                schedulers_and_props_list.append(d)

        # post process the schedulernames, and raw properties
        # we do this out of the loop, as this can result in errors
        schedulers_and_props = [(
            self.getSchedulerByName(entry_dict['sched_name']),
            self.createTriggerProperties(entry_dict['props_to_set']),
            entry_dict['unimportant'])
            for entry_dict in schedulers_and_props_list]

        ss_for_trigger = self.prepareSourcestampListForTrigger()

        dl = []
        triggeredNames = []
        results = SUCCESS
        self.running = True

        unimportant_brids = []

        for sch, props_to_set, unimportant in schedulers_and_props:
            idsDeferred, resultsDeferred = sch.trigger(
                waited_for=self.waitForFinish, sourcestamps=ss_for_trigger,
                set_props=props_to_set,
                parent_buildid=self.build.buildid,
                parent_relationship=self.parent_relationship
            )
            # we are not in a hurry of starting all in parallel and managing
            # the deferred lists, just let the db writes be serial.
            brids = {}
            try:
                bsid, brids = yield idsDeferred
            except Exception as e:
                yield self.addLogWithException(e)
                results = EXCEPTION
            if unimportant:
                unimportant_brids.extend(itervalues(brids))
            self.brids.extend(itervalues(brids))
            for brid in brids.values():
                # put the url to the brids, so that we can have the status from
                # the beginning
                url = self.master.status.getURLForBuildrequest(brid)
                yield self.addURL("%s #%d" % (sch.name, brid), url)
            dl.append(resultsDeferred)
            triggeredNames.append(sch.name)
            if self.ended:
                defer.returnValue(CANCELLED)
        self.triggeredNames = triggeredNames

        if self.waitForFinish:
            self.waitForFinishDeferred = defer.DeferredList(dl, consumeErrors=1)
            try:
                rclist = yield self.waitForFinishDeferred
            except defer.CancelledError:
                pass
            # we were interrupted, don't bother update status
            if self.ended:
                defer.returnValue(CANCELLED)
            yield self.addBuildUrls(rclist)
            results = yield self.worstStatus(results, rclist, unimportant_brids)
        else:
            # do something to handle errors
            for d in dl:
                d.addErrback(log.err,
                             '(ignored) while invoking Triggerable schedulers:')

        defer.returnValue(results)

    def getResultSummary(self):
        if self.ended:
            return {u'step': u'interrupted'}
        return {u'step': self.getCurrentSummary()[u'step']} if self.triggeredNames else {}

    def getCurrentSummary(self):
        if not self.triggeredNames:
            return {u'step': u'running'}
        return {u'step': u'triggered %s' % (u', '.join(self.triggeredNames))}
