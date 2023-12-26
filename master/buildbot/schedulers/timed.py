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

import datetime

import croniter

from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from zope.interface import implementer

from buildbot import config
from buildbot import util
from buildbot.changes.filter import ChangeFilter
from buildbot.interfaces import ITriggerableScheduler
from buildbot.process import buildstep
from buildbot.process import properties
from buildbot.schedulers import base
from buildbot.util.codebase import AbsoluteSourceStampsMixin

# States of objects which have to be observed are registered in the data base table `object_state`.
# `objectid` in the `object_state` refers to the object from the `object` table.
# Schedulers use the following state keys:
# - `last_only_if_changed` - bool, setting of `onlyIfChanged` when the scheduler checked whether to
# run build the last time. Does not exist if there was no build before.
# - `last_build` - timestamp, time when the last build was scheduled to run. If `onlyIfChanged` is
# set to True, only when there are designated changes build will be started. If the build was not
# started,
# `last_build` means on what time build was scheduled to run ignoring the fact if it actually ran or
# not.
# Value of these state keys affects the decision whether to run a build.
#
# When deciding whether to run the build or to skip it, several factors and their interactions are
# evaluated:
# - the value of `onlyIfChanged` (default is False);
# - has the state of `onlyIfChanged` changed;
# - whether this would be first build (True if `last_build` value was not detected). If there
# already were builds in the past, it indicates that the scheduler is existing;
# - were there any important changes after the last build.
#
# If `onlyIfChanged` is not set or its setting changes to False, builds will always run on the time
# set, ignoring the status of `last_only_if_changed` and `last_build` regardless of what the state
# is or anything else.
#
# If `onlyIfChanged` is True, then builds will be run when there are relevant changes.
#
# If `onlyIfChanged` is True and even when there were no relevant changes, builds will run for the
# the first time on specified time as well when the following condition holds:
# - `last_only_if_changed` was set to False on previous build. This ensures that any changes that
# happened while `onlyIfChanged` was still False are not missed. This may result in a single build
# done unnecessarily, but it is accepted as a good compromise because it only happens when
# `onlyIfChanged` is adjusted;
# - `last_build` does not have a value yet meaning that it is a new scheduler and we should have
# initial build to set a baseline.
#
# There is an edge case, when upgrading to v3.5.0 and new object status variable
# `last_only_if_changed` is introduced. If scheduler exists and had builds before
# (`last_build` has a value), build should only be started if there are relevant changes.
# Thus upgrading the version does not start unnecessary builds.


class Timed(AbsoluteSourceStampsMixin, base.BaseScheduler):

    """
    Parent class for timed schedulers.  This takes care of the (surprisingly
    subtle) mechanics of ensuring that each timed actuation runs to completion
    before the service stops.
    """

    compare_attrs = ('reason', 'createAbsoluteSourceStamps', 'onlyIfChanged',
                     'branch', 'fileIsImportant', 'change_filter', 'onlyImportant')
    reason = ''

    class NoBranch:
        pass

    def __init__(self, name, builderNames, reason='',
                 createAbsoluteSourceStamps=False, onlyIfChanged=False,
                 branch=NoBranch, change_filter=None, fileIsImportant=None,
                 onlyImportant=False, **kwargs):
        super().__init__(name, builderNames, **kwargs)

        # tracking for when to start the next build
        self.lastActuated = None

        # A lock to make sure that each actuation occurs without interruption.
        # This lock governs actuateAt, actuateAtTimer, and actuateOk
        self.actuationLock = defer.DeferredLock()
        self.actuateOk = False
        self.actuateAt = None
        self.actuateAtTimer = None

        self.reason = util.bytes2unicode(reason % {'name': name})
        self.branch = branch
        self.change_filter = ChangeFilter.fromSchedulerConstructorArgs(
            change_filter=change_filter)
        self.createAbsoluteSourceStamps = createAbsoluteSourceStamps
        self.onlyIfChanged = onlyIfChanged
        if fileIsImportant and not callable(fileIsImportant):
            config.error(
                "fileIsImportant must be a callable")
        self.fileIsImportant = fileIsImportant
        # If True, only important changes will be added to the buildset.
        self.onlyImportant = onlyImportant
        self._reactor = reactor  # patched by tests
        self.is_first_build = None

    @defer.inlineCallbacks
    def activate(self):
        yield super().activate()

        if not self.enabled:
            return None

        # no need to lock this
        # nothing else can run before the service is started
        self.actuateOk = True

        # get the scheduler's last_build time (note: only done at startup)
        self.lastActuated = yield self.getState('last_build', None)
        if self.lastActuated is None:
            self.is_first_build = True
        else:
            self.is_first_build = False

        # schedule the next build
        yield self.scheduleNextBuild()

        if self.onlyIfChanged or self.createAbsoluteSourceStamps:
            yield self.startConsumingChanges(fileIsImportant=self.fileIsImportant,
                                             change_filter=self.change_filter,
                                             onlyImportant=self.onlyImportant)
        else:
            yield self.master.db.schedulers.flushChangeClassifications(self.serviceid)
        return None

    @defer.inlineCallbacks
    def deactivate(self):
        yield super().deactivate()

        if not self.enabled:
            return None

        # shut down any pending actuation, and ensure that we wait for any
        # current actuation to complete by acquiring the lock.  This ensures
        # that no build will be scheduled after deactivate is complete.
        def stop_actuating():
            self.actuateOk = False
            self.actuateAt = None
            if self.actuateAtTimer:
                self.actuateAtTimer.cancel()
            self.actuateAtTimer = None
        yield self.actuationLock.run(stop_actuating)
        return None

    # Scheduler methods

    def gotChange(self, change, important):
        # both important and unimportant changes on our branch are recorded, as
        # we will include all such changes in any buildsets we start.  Note
        # that we must check the branch here because it is not included in the
        # change filter.
        if self.branch is not Timed.NoBranch and change.branch != self.branch:
            return defer.succeed(None)  # don't care about this change

        d = self.master.db.schedulers.classifyChanges(
            self.serviceid, {change.number: important})

        if self.createAbsoluteSourceStamps:
            d.addCallback(lambda _: self.recordChange(change))

        return d

    @defer.inlineCallbacks
    def startBuild(self):
        if not self.enabled:
            log.msg(format='ignoring build from %(name)s because scheduler '
                           'has been disabled by the user',
                    name=self.name)
            return

        # use the collected changes to start a build
        scheds = self.master.db.schedulers
        classifications = yield scheds.getChangeClassifications(self.serviceid)

        # if onlyIfChanged is True, then we will skip this build if no important changes have
        # occurred since the last invocation. Note that when the scheduler has just been started
        # there may not be any important changes yet and we should start the build for the
        # current state of the code whatever it is.
        #
        # Note that last_only_if_changed will always be set to the value of onlyIfChanged
        # at the point when startBuild finishes (it is not obvious, that all code paths lead
        # to this outcome)

        last_only_if_changed = yield self.getState('last_only_if_changed', True)

        if (
            last_only_if_changed
            and self.onlyIfChanged
            and not any(classifications.values())
            and not self.is_first_build
            and not self.maybe_force_build_on_unimportant_changes(self.lastActuated)
        ):
            log.msg(("{} scheduler <{}>: skipping build " +
                     "- No important changes").format(self.__class__.__name__, self.name))
            self.is_first_build = False
            return

        if last_only_if_changed != self.onlyIfChanged:
            yield self.setState('last_only_if_changed', self.onlyIfChanged)

        changeids = sorted(classifications.keys())

        if changeids:
            max_changeid = changeids[-1]  # (changeids are sorted)
            yield self.addBuildsetForChanges(reason=self.reason,
                                             changeids=changeids,
                                             priority=self.priority)
            yield scheds.flushChangeClassifications(self.serviceid,
                                                    less_than=max_changeid + 1)
        else:
            # There are no changes, but onlyIfChanged is False, so start
            # a build of the latest revision, whatever that is
            sourcestamps = [{"codebase": cb} for cb in self.codebases]
            yield self.addBuildsetForSourceStampsWithDefaults(
                reason=self.reason,
                sourcestamps=sourcestamps,
                priority=self.priority)
        self.is_first_build = False

    def getCodebaseDict(self, codebase):
        if self.createAbsoluteSourceStamps:
            return super().getCodebaseDict(codebase)
        return self.codebases[codebase]

    # Timed methods

    def getNextBuildTime(self, lastActuation):
        """
        Called by to calculate the next time to actuate a BuildSet.  Override
        in subclasses.  To trigger a fresh call to this method, use
        L{rescheduleNextBuild}.

        @param lastActuation: the time of the last actuation, or None for never

        @returns: a Deferred firing with the next time a build should occur (in
        the future), or None for never.
        """
        raise NotImplementedError

    def scheduleNextBuild(self):
        """
        Schedule the next build, re-invoking L{getNextBuildTime}.  This can be
        called at any time, and it will avoid contention with builds being
        started concurrently.

        @returns: Deferred
        """
        return self.actuationLock.run(self._scheduleNextBuild_locked)

    def maybe_force_build_on_unimportant_changes(self, current_actuation_time):
        """
        Allows forcing a build in cases when there are no important changes and onlyIfChanged is
        enabled.
        """
        return False

    # utilities

    def now(self):
        "Similar to util.now, but patchable by tests"
        return util.now(self._reactor)

    def current_utc_offset(self, tm):
        return (
            datetime.datetime.fromtimestamp(tm).replace(tzinfo=datetime.timezone.utc)
            - datetime.datetime.fromtimestamp(tm, datetime.timezone.utc)
        ).total_seconds()

    @defer.inlineCallbacks
    def _scheduleNextBuild_locked(self):
        # clear out the existing timer
        if self.actuateAtTimer:
            self.actuateAtTimer.cancel()
        self.actuateAtTimer = None

        # calculate the new time
        actuateAt = yield self.getNextBuildTime(self.lastActuated)

        if actuateAt is None:
            self.actuateAt = None
        else:
            # set up the new timer
            now = self.now()
            self.actuateAt = max(actuateAt, now)
            untilNext = self.actuateAt - now
            if untilNext == 0:
                log.msg(f"{self.__class__.__name__} scheduler <{self.name}>: "
                        "missed scheduled build time - building immediately")
            self.actuateAtTimer = self._reactor.callLater(untilNext,
                                                          self._actuate)

    @defer.inlineCallbacks
    def _actuate(self):
        # called from the timer when it's time to start a build
        self.actuateAtTimer = None
        self.lastActuated = self.actuateAt

        @defer.inlineCallbacks
        def set_state_and_start():
            # bail out if we shouldn't be actuating anymore
            if not self.actuateOk:
                return

            # mark the last build time
            self.actuateAt = None
            yield self.setState('last_build', self.lastActuated)

            try:
                # start the build
                yield self.startBuild()
            except Exception as e:
                log.err(e, 'while actuating')
            finally:
                # schedule the next build (noting the lock is already held)
                yield self._scheduleNextBuild_locked()
        yield self.actuationLock.run(set_state_and_start)


class Periodic(Timed):
    compare_attrs = ('periodicBuildTimer',)

    def __init__(self, name, builderNames, periodicBuildTimer,
                 reason="The Periodic scheduler named '%(name)s' triggered this build",
                 **kwargs):
        super().__init__(name, builderNames, reason=reason, **kwargs)
        if periodicBuildTimer <= 0:
            config.error("periodicBuildTimer must be positive")
        self.periodicBuildTimer = periodicBuildTimer

    def getNextBuildTime(self, lastActuated):
        if lastActuated is None:
            return defer.succeed(self.now())  # meaning "ASAP"
        return defer.succeed(lastActuated + self.periodicBuildTimer)


class NightlyBase(Timed):
    compare_attrs = (
        "minute",
        "hour",
        "dayOfMonth",
        "month",
        "dayOfWeek",
        "force_at_minute",
        "force_at_hour",
        "force_at_day_of_month",
        "force_at_month",
        "force_at_day_of_week",
    )

    def __init__(self, name, builderNames, minute=0, hour='*',
                 dayOfMonth='*', month='*', dayOfWeek='*',
                 force_at_minute=None,
                 force_at_hour=None,
                 force_at_day_of_month=None,
                 force_at_month=None,
                 force_at_day_of_week=None,
                 **kwargs):
        super().__init__(name, builderNames, **kwargs)

        self.minute = minute
        self.hour = hour
        self.dayOfMonth = dayOfMonth
        self.month = month
        self.dayOfWeek = dayOfWeek

        self.force_at_enabled = (
            force_at_minute is not None
            or force_at_hour is not None
            or force_at_day_of_month is not None
            or force_at_month is not None
            or force_at_day_of_week is not None
        )

        def default_if_none(value, default):
            if value is None:
                return default
            return value

        self.force_at_minute = default_if_none(force_at_minute, 0)
        self.force_at_hour = default_if_none(force_at_hour, "*")
        self.force_at_day_of_month = default_if_none(force_at_day_of_month, "*")
        self.force_at_month = default_if_none(force_at_month, "*")
        self.force_at_day_of_week = default_if_none(force_at_day_of_week, "*")

    def _timeToCron(self, time, isDayOfWeek=False):
        if isinstance(time, int):
            if isDayOfWeek:
                # Convert from Mon = 0 format to Sun = 0 format for use in
                # croniter
                time = (time + 1) % 7
            return time

        if isinstance(time, str):
            if isDayOfWeek:
                # time could be a comma separated list of values, e.g. "5,sun"
                time_array = str(time).split(',')
                for i, time_val in enumerate(time_array):
                    try:
                        # try to convert value in place
                        # Conversion for croniter (see above)
                        time_array[i] = (int(time_val) + 1) % 7
                    except ValueError:
                        # all non-int values are kept
                        pass
                # Convert the list to a string
                return ','.join([str(s) for s in time_array])

            return time

        if isDayOfWeek:
            # Conversion for croniter (see above)
            time = [(t + 1) % 7 for t in time]

        return ','.join([str(s) for s in time])  # Convert the list to a string

    def _times_to_cron_line(self, minute, hour, day_of_month, month, day_of_week):
        return " ".join([
            str(self._timeToCron(minute)),
            str(self._timeToCron(hour)),
            str(self._timeToCron(day_of_month)),
            str(self._timeToCron(month)),
            str(self._timeToCron(day_of_week, True)),
        ])

    def _time_to_croniter_tz_time(self, ts):
        # By default croniter interprets input timestamp in UTC timezone. However, the scheduler
        # works in local timezone, so appropriate timezone information needs to be passed
        tz = datetime.timezone(datetime.timedelta(seconds=self.current_utc_offset(ts)))
        return datetime.datetime.fromtimestamp(ts, tz)

    def getNextBuildTime(self, lastActuated):
        ts = lastActuated or self.now()
        sched = self._times_to_cron_line(
            self.minute,
            self.hour,
            self.dayOfMonth,
            self.month,
            self.dayOfWeek,
        )

        cron = croniter.croniter(sched, self._time_to_croniter_tz_time(ts))
        nextdate = cron.get_next(float)
        return defer.succeed(nextdate)

    def maybe_force_build_on_unimportant_changes(self, current_actuation_time):
        if not self.force_at_enabled:
            return False
        cron_string = self._times_to_cron_line(
            self.force_at_minute,
            self.force_at_hour,
            self.force_at_day_of_month,
            self.force_at_month,
            self.force_at_day_of_week,
        )

        return croniter.croniter.match(
            cron_string,
            self._time_to_croniter_tz_time(current_actuation_time)
        )


class Nightly(NightlyBase):

    def __init__(self, name, builderNames, minute=0, hour='*',
                 dayOfMonth='*', month='*', dayOfWeek='*',
                 reason="The Nightly scheduler named '%(name)s' triggered this build",
                 force_at_minute=None,
                 force_at_hour=None,
                 force_at_day_of_month=None,
                 force_at_month=None,
                 force_at_day_of_week=None,
                 **kwargs):
        super().__init__(name=name, builderNames=builderNames,
                         minute=minute, hour=hour, dayOfMonth=dayOfMonth,
                         month=month, dayOfWeek=dayOfWeek, reason=reason,
                         force_at_minute=force_at_minute,
                         force_at_hour=force_at_hour,
                         force_at_day_of_month=force_at_day_of_month,
                         force_at_month=force_at_month,
                         force_at_day_of_week=force_at_day_of_week,
                         **kwargs)


@implementer(ITriggerableScheduler)
class NightlyTriggerable(NightlyBase):

    def __init__(self, name, builderNames, minute=0, hour='*',
                 dayOfMonth='*', month='*', dayOfWeek='*',
                 reason="The NightlyTriggerable scheduler named '%(name)s' triggered this build",
                 force_at_minute=None,
                 force_at_hour=None,
                 force_at_day_of_month=None,
                 force_at_month=None,
                 force_at_day_of_week=None,
                 **kwargs):
        super().__init__(name=name, builderNames=builderNames,
                         minute=minute, hour=hour, dayOfMonth=dayOfMonth,
                         month=month, dayOfWeek=dayOfWeek, reason=reason,
                         force_at_minute=force_at_minute,
                         force_at_hour=force_at_hour,
                         force_at_day_of_month=force_at_day_of_month,
                         force_at_month=force_at_month,
                         force_at_day_of_week=force_at_day_of_week,
                         **kwargs)

        self._lastTrigger = None

    @defer.inlineCallbacks
    def activate(self):
        yield super().activate()

        if not self.enabled:
            return

        lastTrigger = yield self.getState('lastTrigger', None)
        self._lastTrigger = None
        if lastTrigger:
            try:
                if isinstance(lastTrigger[0], list):
                    self._lastTrigger = (lastTrigger[0],
                                         properties.Properties.fromDict(
                                             lastTrigger[1]),
                                         lastTrigger[2],
                                         lastTrigger[3])
                # handle state from before Buildbot-0.9.0
                elif isinstance(lastTrigger[0], dict):
                    self._lastTrigger = (list(lastTrigger[0].values()),
                                         properties.Properties.fromDict(
                                             lastTrigger[1]),
                                         None,
                                         None)
            except Exception:
                pass
            # If the lastTrigger isn't of the right format, ignore it
            if not self._lastTrigger:
                log.msg(
                    format="NightlyTriggerable Scheduler <%(scheduler)s>: "
                    "could not load previous state; starting fresh",
                    scheduler=self.name)

    def trigger(self, waited_for, sourcestamps=None, set_props=None,
                parent_buildid=None, parent_relationship=None):
        """Trigger this scheduler with the given sourcestamp ID. Returns a
        deferred that will fire when the buildset is finished."""
        assert isinstance(sourcestamps, list), \
            "trigger requires a list of sourcestamps"

        self._lastTrigger = (sourcestamps,
                             set_props,
                             parent_buildid,
                             parent_relationship)

        if set_props:
            propsDict = set_props.asDict()
        else:
            propsDict = {}

        # record the trigger in the db
        d = self.setState('lastTrigger', (sourcestamps,
                                          propsDict,
                                          parent_buildid,
                                          parent_relationship))

        # Trigger expects a callback with the success of the triggered
        # build, if waitForFinish is True.
        # Just return SUCCESS, to indicate that the trigger was successful,
        # don't wait for the nightly to run.
        return (defer.succeed((None, {})), d.addCallback(lambda _: buildstep.SUCCESS))

    @defer.inlineCallbacks
    def startBuild(self):
        if not self.enabled:
            log.msg(format='ignoring build from %(name)s because scheduler '
                           'has been disabled by the user',
                    name=self.name)
            return

        if self._lastTrigger is None:
            return

        (sourcestamps, set_props, parent_buildid,
         parent_relationship) = self._lastTrigger
        self._lastTrigger = None
        yield self.setState('lastTrigger', None)

        # properties for this buildset are composed of our own properties,
        # potentially overridden by anything from the triggering build
        props = properties.Properties()
        props.updateFromProperties(self.properties)
        if set_props:
            props.updateFromProperties(set_props)

        yield self.addBuildsetForSourceStampsWithDefaults(
            reason=self.reason,
            sourcestamps=sourcestamps,
            properties=props,
            parent_buildid=parent_buildid,
            parent_relationship=parent_relationship,
            priority=self.priority)
