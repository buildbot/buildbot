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
from future.utils import itervalues
from future.utils import string_types

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
from buildbot.util import croniter
from buildbot.util.codebase import AbsoluteSourceStampsMixin


class Timed(base.BaseScheduler, AbsoluteSourceStampsMixin):

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
        base.BaseScheduler.__init__(self, name, builderNames, **kwargs)

        # tracking for when to start the next build
        self.lastActuated = None

        # A lock to make sure that each actuation occurs without interruption.
        # This lock governs actuateAt, actuateAtTimer, and actuateOk
        self.actuationLock = defer.DeferredLock()
        self.actuateOk = False
        self.actuateAt = None
        self.actuateAtTimer = None

        self.reason = util.ascii2unicode(reason % {'name': name})
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

    @defer.inlineCallbacks
    def activate(self):
        yield base.BaseScheduler.activate(self)

        if not self.enabled:
            yield defer.returnValue(None)
            return

        # no need to lock this
        # nothing else can run before the service is started
        self.actuateOk = True

        # get the scheduler's last_build time (note: only done at startup)
        self.lastActuated = yield self.getState('last_build', None)

        # schedule the next build
        yield self.scheduleNextBuild()

        if self.onlyIfChanged or self.createAbsoluteSourceStamps:
            yield self.startConsumingChanges(fileIsImportant=self.fileIsImportant,
                                             change_filter=self.change_filter,
                                             onlyImportant=self.onlyImportant)
        else:
            yield self.master.db.schedulers.flushChangeClassifications(self.serviceid)

    @defer.inlineCallbacks
    def deactivate(self):
        yield base.BaseScheduler.deactivate(self)

        if not self.enabled:
            yield defer.returnValue(None)
            return

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

        # if onlyIfChanged is True, then we will skip this build if no
        # important changes have occurred since the last invocation
        if self.onlyIfChanged and not any(itervalues(classifications)):
            log.msg(("%s scheduler <%s>: skipping build " +
                     "- No important changes") %
                    (self.__class__.__name__, self.name))
            return

        changeids = sorted(classifications.keys())

        if changeids:
            max_changeid = changeids[-1]  # (changeids are sorted)
            yield self.addBuildsetForChanges(reason=self.reason,
                                             changeids=changeids)
            yield scheds.flushChangeClassifications(self.serviceid,
                                                    less_than=max_changeid + 1)
        else:
            # There are no changes, but onlyIfChanged is False, so start
            # a build of the latest revision, whatever that is
            sourcestamps = [dict(codebase=cb) for cb in self.codebases]
            yield self.addBuildsetForSourceStampsWithDefaults(
                reason=self.reason,
                sourcestamps=sourcestamps)

    def getCodebaseDict(self, codebase):
        if self.createAbsoluteSourceStamps:
            return AbsoluteSourceStampsMixin.getCodebaseDict(self, codebase)
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

    # utilities

    def now(self):
        "Similar to util.now, but patchable by tests"
        return util.now(self._reactor)

    def _scheduleNextBuild_locked(self):
        # clear out the existing timer
        if self.actuateAtTimer:
            self.actuateAtTimer.cancel()
        self.actuateAtTimer = None

        # calculate the new time
        d = self.getNextBuildTime(self.lastActuated)

        # set up the new timer
        @d.addCallback
        def set_timer(actuateAt):
            now = self.now()
            self.actuateAt = max(actuateAt, now)
            if actuateAt is not None:
                untilNext = self.actuateAt - now
                if untilNext == 0:
                    log.msg(("%s scheduler <%s>: missed scheduled build time"
                             " - building immediately") %
                            (self.__class__.__name__, self.name))
                self.actuateAtTimer = self._reactor.callLater(untilNext,
                                                              self._actuate)
        return d

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

            # start the build
            yield self.startBuild()

            # schedule the next build (noting the lock is already held)
            yield self._scheduleNextBuild_locked()
        d = self.actuationLock.run(set_state_and_start)

        # this function can't return a deferred, so handle any failures via
        # log.err
        d.addErrback(log.err, 'while actuating')


class Periodic(Timed):
    compare_attrs = ('periodicBuildTimer',)

    def __init__(self, name, builderNames, periodicBuildTimer,
                 reason="The Periodic scheduler named '%(name)s' triggered this build",
                 **kwargs):
        Timed.__init__(self, name, builderNames, reason=reason, **kwargs)
        if periodicBuildTimer <= 0:
            config.error("periodicBuildTimer must be positive")
        self.periodicBuildTimer = periodicBuildTimer

    def getNextBuildTime(self, lastActuated):
        if lastActuated is None:
            return defer.succeed(self.now())  # meaning "ASAP"
        return defer.succeed(lastActuated + self.periodicBuildTimer)


class NightlyBase(Timed):
    compare_attrs = ('minute', 'hour', 'dayOfMonth', 'month', 'dayOfWeek')

    def __init__(self, name, builderNames, minute=0, hour='*',
                 dayOfMonth='*', month='*', dayOfWeek='*',
                 **kwargs):
        Timed.__init__(self, name, builderNames, **kwargs)

        self.minute = minute
        self.hour = hour
        self.dayOfMonth = dayOfMonth
        self.month = month
        self.dayOfWeek = dayOfWeek

    def _timeToCron(self, time, isDayOfWeek=False):
        if isinstance(time, int):
            if isDayOfWeek:
                # Convert from Mon = 0 format to Sun = 0 format for use in
                # croniter
                time = (time + 1) % 7
            return time

        if isinstance(time, string_types):
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

    def getNextBuildTime(self, lastActuated):
        dateTime = lastActuated or self.now()
        sched = '%s %s %s %s %s' % (self._timeToCron(self.minute),
                                    self._timeToCron(self.hour),
                                    self._timeToCron(self.dayOfMonth),
                                    self._timeToCron(self.month),
                                    self._timeToCron(self.dayOfWeek, True))
        cron = croniter.croniter(sched, dateTime)
        nextdate = cron.get_next(float)
        return defer.succeed(nextdate)


class Nightly(NightlyBase):

    def __init__(self, name, builderNames, minute=0, hour='*',
                 dayOfMonth='*', month='*', dayOfWeek='*',
                 reason="The Nightly scheduler named '%(name)s' triggered this build",
                 **kwargs):
        NightlyBase.__init__(self, name=name, builderNames=builderNames,
                             minute=minute, hour=hour, dayOfMonth=dayOfMonth,
                             month=month, dayOfWeek=dayOfWeek, reason=reason,
                             **kwargs)


@implementer(ITriggerableScheduler)
class NightlyTriggerable(NightlyBase):

    def __init__(self, name, builderNames, minute=0, hour='*',
                 dayOfMonth='*', month='*', dayOfWeek='*',
                 reason="The NightlyTriggerable scheduler named '%(name)s' triggered this build",
                 **kwargs):
        NightlyBase.__init__(self, name=name, builderNames=builderNames,
                             minute=minute, hour=hour, dayOfMonth=dayOfMonth,
                             month=month, dayOfWeek=dayOfWeek, reason=reason,
                             **kwargs)

        self._lastTrigger = None

    @defer.inlineCallbacks
    def activate(self):
        yield NightlyBase.activate(self)

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
                    self._lastTrigger = (list(itervalues(lastTrigger[0])),
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
            parent_relationship=parent_relationship)
