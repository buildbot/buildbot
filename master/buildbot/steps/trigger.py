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

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot.interfaces import IRenderable
from buildbot.interfaces import ITriggerableScheduler
from buildbot.process.buildstep import CANCELLED
from buildbot.process.buildstep import EXCEPTION
from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import BuildStep
from buildbot.process.properties import Properties
from buildbot.process.properties import Property
from buildbot.process.results import ALL_RESULTS
from buildbot.process.results import statusToString
from buildbot.process.results import worst_status
from buildbot.reporters.utils import getURLForBuild
from buildbot.reporters.utils import getURLForBuildrequest

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class Trigger(BuildStep):
    name = "trigger"

    renderables = [
        'alwaysUseLatest',
        'parent_relationship',
        'schedulerNames',
        'set_properties',
        'sourceStamps',
        'updateSourceStamp',
        'waitForFinish',
    ]

    flunkOnFailure = True

    def __init__(
        self,
        schedulerNames: list[str] | None = None,
        sourceStamp: dict[str, Any] | None = None,
        sourceStamps: list[dict[str, Any]] | None = None,
        updateSourceStamp: bool | None = None,
        alwaysUseLatest: bool = False,
        waitForFinish: bool = False,
        set_properties: dict[str, Any] | None = None,
        copy_properties: list[str] | None = None,
        parent_relationship: str = "Triggered from",
        unimportantSchedulerNames: list[str] | None = None,
        **kwargs: Any,
    ) -> None:
        if schedulerNames is None:
            schedulerNames = []
        if unimportantSchedulerNames is None:
            unimportantSchedulerNames = []
        if not schedulerNames:
            config.error("You must specify a scheduler to trigger")
        if (sourceStamp or sourceStamps) and (updateSourceStamp is not None):
            config.error("You can't specify both sourceStamps and updateSourceStamp")
        if (sourceStamp or sourceStamps) and alwaysUseLatest:
            config.error("You can't specify both sourceStamps and alwaysUseLatest")
        if alwaysUseLatest and (updateSourceStamp is not None):
            config.error("You can't specify both alwaysUseLatest and updateSourceStamp")

        def hasRenderable(l: list[Any]) -> bool:
            for s in l:
                if IRenderable.providedBy(s):
                    return True
            return False

        if not hasRenderable(schedulerNames) and not hasRenderable(unimportantSchedulerNames):
            if not set(schedulerNames).issuperset(set(unimportantSchedulerNames)):
                config.error("unimportantSchedulerNames must be a subset of schedulerNames")

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

        properties: dict[str, Any] = {}
        properties.update(set_properties)
        for i in copy_properties:
            properties[i] = Property(i)
        self.set_properties = properties
        self.parent_relationship = parent_relationship
        self.running = False
        self.ended = False
        self.brids: list[int] = []
        self.triggeredNames: list[str] | None = None
        self.waitForFinishDeferred: defer.Deferred[Any] | None = None
        self._result_list: list[int] = []
        super().__init__(**kwargs)

    def interrupt(self, reason: Any) -> None:  # type: ignore[override]
        # We cancel the buildrequests, as the data api handles
        # both cases:
        # - build started: stop is sent,
        # - build not created yet: related buildrequests are set to CANCELLED.
        # Note that there is an identified race condition though (more details
        # are available at buildbot.data.buildrequests).
        for brid in self.brids:
            self.master.data.control(  # type: ignore[union-attr]
                "cancel", {'reason': 'parent build was interrupted'}, ("buildrequests", brid)
            )
        if self.running and not self.ended:
            self.ended = True
            # if we are interrupted because of a connection lost, we interrupt synchronously
            if self.build.conn is None and self.waitForFinishDeferred is not None:  # type: ignore[union-attr]
                self.waitForFinishDeferred.cancel()

    # Create the properties that are used for the trigger
    def createTriggerProperties(self, properties: dict[str, Any]) -> Properties:
        # make a new properties object from a dict rendered by the old
        # properties object
        trigger_properties = Properties()
        trigger_properties.update(properties, "Trigger")
        return trigger_properties

    def getSchedulerByName(self, name: str) -> Any:
        # we use the fact that scheduler_manager is a multiservice, with schedulers as childs
        # this allow to quickly find schedulers instance by name
        schedulers = self.master.scheduler_manager.namedServices  # type: ignore[union-attr]
        if name not in schedulers:
            raise ValueError(f"unknown triggered scheduler: {name!r}")
        sch = schedulers[name]
        if not ITriggerableScheduler.providedBy(sch):
            raise ValueError(f"triggered scheduler is not ITriggerableScheduler: {name!r}")
        return sch

    # This customization endpoint allows users to dynamically select which
    # scheduler and properties to trigger
    def getSchedulersAndProperties(self) -> list[dict[str, Any]]:
        return [
            {
                'sched_name': sched,
                'props_to_set': self.set_properties,
                'unimportant': sched in self.unimportantSchedulerNames,
            }
            for sched in self.schedulerNames
        ]

    def prepareSourcestampListForTrigger(self) -> list[dict[str, Any]]:
        if self.sourceStamps:
            ss_for_trigger: dict[str, Any] = {}
            for ss in self.sourceStamps:
                codebase = ss.get('codebase', '')
                assert codebase not in ss_for_trigger, "codebase specified multiple times"
                ss_for_trigger[codebase] = ss
            trigger_values = [ss_for_trigger[k] for k in sorted(ss_for_trigger.keys())]
            return trigger_values

        if self.alwaysUseLatest:
            return []

        # start with the sourcestamps from current build
        ss_for_trigger2: dict[str, Any] = {}
        objs_from_build = self.build.getAllSourceStamps()  # type: ignore[union-attr]
        for ss in objs_from_build:  # type: ignore[assignment]
            ss_for_trigger2[ss.codebase] = ss.asDict()  # type: ignore[attr-defined]

        # overrule revision in sourcestamps with got revision
        if self.updateSourceStamp:
            got = self.getAllGotRevisions()
            for codebase, ss in ss_for_trigger2.items():
                if codebase in got:
                    ss['revision'] = got[codebase]

        trigger_values2 = [ss_for_trigger2[k] for k in sorted(ss_for_trigger2.keys())]
        return trigger_values2

    def getAllGotRevisions(self) -> dict[str, Any]:
        all_got_revisions = self.getProperty('got_revision', {})
        # For backwards compatibility all_got_revisions is a string if codebases
        # are not used. Convert to the default internal type (dict)
        if not isinstance(all_got_revisions, dict):
            all_got_revisions = {'': all_got_revisions}
        return all_got_revisions

    @defer.inlineCallbacks
    def worstStatus(
        self, overall_results: int, rclist: list[Any], unimportant_brids: list[int]
    ) -> InlineCallbacksType[int]:
        for was_cb, results in rclist:
            if isinstance(results, tuple):
                results, brids_dict = results

                # brids_dict.values() represents the list of brids kicked by a certain scheduler.
                # We want to ignore the result of ANY brid that was kicked off
                # by an UNimportant scheduler.
                if set(unimportant_brids).issuperset(set(brids_dict.values())):
                    continue

            if not was_cb:
                yield self.addLogWithFailure(results)
                results = EXCEPTION

            overall_results = worst_status(overall_results, results)
        return overall_results

    @defer.inlineCallbacks
    def addBuildUrls(self, rclist: list[Any]) -> InlineCallbacksType[None]:
        brids: dict[Any, Any] = {}
        for was_cb, results in rclist:
            if isinstance(results, tuple):
                results, brids = results
            builderNames: dict[Any, Any] = {}
            if was_cb:  # errors were already logged in worstStatus
                for builderid, br in brids.items():
                    builds = yield self.master.db.builds.getBuilds(buildrequestid=br)  # type: ignore[union-attr]
                    for build in builds:
                        builderid = build.builderid
                        # When virtual builders are used, the builderid used for triggering
                        # is not the same as the one that the build actually got
                        if builderid not in builderNames:
                            builderDict = yield self.master.data.get(("builders", builderid))  # type: ignore[union-attr]
                            builderNames[builderid] = builderDict["name"]
                        num = build.number
                        url = getURLForBuild(self.master, builderid, num)  # type: ignore[arg-type]
                        yield self.addURL(
                            f'{statusToString(build.results)}: {builderNames[builderid]} #{num}',
                            url,
                        )

    @defer.inlineCallbacks
    def _add_results(self, brid: int) -> InlineCallbacksType[None]:
        @defer.inlineCallbacks
        def _is_buildrequest_complete(brid: int) -> InlineCallbacksType[bool]:
            buildrequest = yield self.master.db.buildrequests.getBuildRequest(brid)  # type: ignore[union-attr]
            return buildrequest.complete

        event = ('buildrequests', str(brid), 'complete')
        yield self.master.mq.waitUntilEvent(event, lambda: _is_buildrequest_complete(brid))  # type: ignore[union-attr]
        builds = yield self.master.db.builds.getBuilds(buildrequestid=brid)  # type: ignore[union-attr]
        for build in builds:
            self._result_list.append(build.results)
        self.updateSummary()

    @defer.inlineCallbacks
    def run(self) -> InlineCallbacksType[int]:
        schedulers_and_props = yield self.getSchedulersAndProperties()

        schedulers_and_props_list: list[dict[str, Any]] = []

        # To be back compatible we need to differ between old and new style
        # schedulers_and_props can either consist of 2 elements tuple or
        # dictionary
        for element in schedulers_and_props:
            if isinstance(element, dict):
                schedulers_and_props_list = schedulers_and_props
                break
            # Old-style back compatibility: Convert tuple to dict and make
            # it important
            d = {'sched_name': element[0], 'props_to_set': element[1], 'unimportant': False}
            schedulers_and_props_list.append(d)

        # post process the schedulernames, and raw properties
        # we do this out of the loop, as this can result in errors
        schedulers_and_props = [
            (
                self.getSchedulerByName(entry_dict['sched_name']),
                self.createTriggerProperties(entry_dict['props_to_set']),
                entry_dict['unimportant'],
            )
            for entry_dict in schedulers_and_props_list
        ]

        ss_for_trigger = self.prepareSourcestampListForTrigger()

        dl: list[defer.Deferred[Any]] = []
        triggeredNames: list[str] = []
        results = SUCCESS
        self.running = True

        unimportant_brids: list[int] = []

        # Transmit the maximum priority of the buildrequest of this build to the
        # triggered buildrequests
        priority = max(r.priority for r in self.build.requests)  # type: ignore[union-attr]

        for sch, props_to_set, unimportant in schedulers_and_props:
            idsDeferred, resultsDeferred = sch.trigger(
                waited_for=self.waitForFinish,
                sourcestamps=ss_for_trigger,
                set_props=props_to_set,
                parent_buildid=self.build.buildid,  # type: ignore[union-attr]
                parent_relationship=self.parent_relationship,
                priority=priority,
            )
            # we are not in a hurry of starting all in parallel and managing
            # the deferred lists, just let the db writes be serial.
            brids: dict[Any, Any] = {}
            try:
                _, brids = yield idsDeferred
            except Exception as e:
                yield self.addLogWithException(e)
                results = EXCEPTION
            if unimportant:
                unimportant_brids.extend(brids.values())
            self.brids.extend(brids.values())
            for brid in brids.values():
                # put the url to the brids, so that we can have the status from
                # the beginning
                url = getURLForBuildrequest(self.master, brid)  # type: ignore[arg-type]
                yield self.addURL(f"{sch.name} #{brid}", url)
                # No yield since we let this happen as the builds complete
                self._add_results(brid)

            dl.append(resultsDeferred)
            triggeredNames.append(sch.name)
            if self.ended:
                return CANCELLED
        self.triggeredNames = triggeredNames

        if self.waitForFinish:
            self.waitForFinishDeferred = defer.DeferredList(dl, consumeErrors=True)
            try:
                rclist = yield self.waitForFinishDeferred
            except defer.CancelledError:
                pass
            # we were interrupted, don't bother update status
            if self.ended:
                return CANCELLED
            yield self.addBuildUrls(rclist)
            results = yield self.worstStatus(results, rclist, unimportant_brids)
        else:
            # do something to handle errors
            for deferred in dl:
                deferred.addErrback(log.err, '(ignored) while invoking Triggerable schedulers:')

        return results

    def getResultSummary(self) -> dict[str, str]:
        if self.ended:
            return {'step': 'interrupted'}
        return {'step': self.getCurrentSummary()['step']} if self.triggeredNames else {}

    def getCurrentSummary(self) -> dict[str, str]:
        if not self.triggeredNames:
            return {'step': 'running'}
        summary = ""
        if self._result_list:
            for status in ALL_RESULTS:
                count = self._result_list.count(status)
                if count:
                    summary = summary + (
                        f", {self._result_list.count(status)} {statusToString(status, count)}"
                    )
        return {'step': f"triggered {', '.join(self.triggeredNames)}{summary}"}
