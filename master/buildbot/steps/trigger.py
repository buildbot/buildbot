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
from buildbot.process.buildstep import EXCEPTION
from buildbot.process.buildstep import FAILURE
from buildbot.process.buildstep import LoggingBuildStep
from buildbot.process.buildstep import SUCCESS
from buildbot.process.properties import Properties
from buildbot.process.properties import Property
from twisted.internet import defer
from twisted.python import log


class Trigger(LoggingBuildStep):
    name = "trigger"

    renderables = ['set_properties', 'schedulerNames', 'sourceStamps',
                   'updateSourceStamp', 'alwaysUseLatest']

    flunkOnFailure = True

    def __init__(self, schedulerNames=[], sourceStamp=None, sourceStamps=None,
                 updateSourceStamp=None, alwaysUseLatest=False,
                 waitForFinish=False, set_properties={},
                 copy_properties=[], **kwargs):
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
        self.running = False
        self.ended = False
        LoggingBuildStep.__init__(self, **kwargs)

        # Scheduler name cache
        self._all_schedulers = None

    def interrupt(self, reason):
        if self.running and not self.ended:
            self.step_status.setText(["interrupted"])
            return self.end(EXCEPTION)

    def end(self, result):
        if not self.ended:
            self.ended = True
            return self.finished(result)

    # Create the properties that are used for the trigger
    def createTriggerProperties(self, properties):
        # make a new properties object from a dict rendered by the old
        # properties object
        trigger_properties = Properties()
        trigger_properties.update(properties, "Trigger")
        return trigger_properties

    def getSchedulerByName(self, name):
        # Use a quick cache to avoid generating this dict every time.
        all_schedulers = self._all_schedulers
        if all_schedulers is None:
            all_schedulers = self.build.builder.botmaster.parent.allSchedulers()
            all_schedulers = dict([(sch.name, sch) for sch in all_schedulers])
            self._all_schedulers = all_schedulers

        sch = all_schedulers.get(name)
        if sch is not None:
            if ITriggerableScheduler.providedBy(sch):
                return sch

        return None

    def prepareSourcestampListForTrigger(self):
        if self.sourceStamps:
            ss_for_trigger = {}
            for ss in self.sourceStamps:
                codebase = ss.get('codebase', '')
                assert codebase not in ss_for_trigger, "codebase specified multiple times"
                ss_for_trigger[codebase] = ss
            return ss_for_trigger

        if self.alwaysUseLatest:
            return {}

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

        return ss_for_trigger

    def getSchedulersAndProperties(self):
        return [(sched, self.set_properties) for sched in self.schedulerNames]

    @defer.inlineCallbacks
    def start(self):
        schedulerNames_and_props = yield self.getSchedulersAndProperties()

        # Get all triggerable schedulers and check if there are invalid schedules
        invalid_schedulers = []
        schedulers_and_props = []
        for name, props_to_set in schedulerNames_and_props:
            sch = self.getSchedulerByName(name)
            if sch is None:
                invalid_schedulers.append(name)
                continue

            props_to_set = self.createTriggerProperties(props_to_set)
            schedulers_and_props.append((sch, props_to_set))

        if invalid_schedulers:
            self.step_status.setText(['not valid scheduler:'] + invalid_schedulers)
            self.end(FAILURE)
            return

        self.running = True

        ss_for_trigger = self.prepareSourcestampListForTrigger()

        dl = []
        triggered_names = []
        for sch, props_to_set in schedulers_and_props:
            dl.append(sch.trigger(ss_for_trigger, set_props=props_to_set))
            triggered_names.append(sch.name)
        self.step_status.setText(['triggered'] + triggered_names)

        if self.waitForFinish:
            rclist = yield defer.DeferredList(dl, consumeErrors=1)
            if self.ended:
                return
        else:
            # do something to handle errors
            for d in dl:
                d.addErrback(log.err,
                             '(ignored) while invoking Triggerable schedulers:')
            rclist = None
            self.end(SUCCESS)
            return

        was_exception = was_failure = False
        brids = []
        for was_cb, results in rclist:
            if isinstance(results, tuple):
                results, some_brids = results
                brids.extend(some_brids.items())

            if not was_cb:
                was_exception = True
                log.err(results)
                continue

            if results == FAILURE:
                was_failure = True

        if was_exception:
            result = EXCEPTION
        elif was_failure:
            result = FAILURE
        else:
            result = SUCCESS

        if brids:
            master = self.build.builder.botmaster.parent

            def add_links(res):
                # reverse the dictionary lookup for brid to builder name
                brid_to_bn = dict((bt[1], bt[0]) for bt in brids)

                for was_cb, builddicts in res:
                    if was_cb:
                        for build in builddicts:
                            bn = brid_to_bn[build['brid']]
                            num = build['number']

                            url = master.status.getURLForBuild(bn, num)
                            self.step_status.addURL("%s #%d" % (bn, num), url)

            builddicts = [master.db.builds.getBuildsForRequest(br[1]) for br in brids]
            res = yield defer.DeferredList(builddicts, consumeErrors=1)
            add_links(res)

        self.end(result)
        return
