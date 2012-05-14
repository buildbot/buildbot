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

import time
from zope.interface import implements

from buildbot import util
from buildbot.interfaces import ITriggerableScheduler
from buildbot.process import buildstep, properties
from buildbot.schedulers import base
from twisted.internet import defer, reactor
from twisted.python import log
from buildbot.changes import filter

class Timed(base.BaseScheduler):
    """
    Parent class for timed schedulers.  This takes care of the (surprisingly
    subtle) mechanics of ensuring that each timed actuation runs to completion
    before the service stops.
    """

    compare_attrs = base.BaseScheduler.compare_attrs

    def __init__(self, name, builderNames, properties={}):
        base.BaseScheduler.__init__(self, name, builderNames, properties)

        # tracking for when to start the next build
        self.lastActuated = None

        # A lock to make sure that each actuation occurs without interruption.
        # This lock governs actuateAt, actuateAtTimer, and actuateOk
        self.actuationLock = defer.DeferredLock()
        self.actuateOk = False
        self.actuateAt = None
        self.actuateAtTimer = None

        self._reactor = reactor # patched by tests

    def startService(self):
        base.BaseScheduler.startService(self)

        # no need to lock this; nothing else can run before the service is started
        self.actuateOk = True

        # get the scheduler's last_build time (note: only done at startup)
        d = self.getState('last_build', None)
        def set_last(lastActuated):
            self.lastActuated = lastActuated
        d.addCallback(set_last)

        # schedule the next build
        d.addCallback(lambda _ : self.scheduleNextBuild())

        # give subclasses a chance to start up
        d.addCallback(lambda _ : self.startTimedSchedulerService())

        # startService does not return a Deferred, so handle errors with a traceback
        d.addErrback(log.err, "while initializing %s '%s'" %
                (self.__class__.__name__, self.name))

    def startTimedSchedulerService(self):
        """Hook for subclasses to participate in the L{startService} process;
        can return a Deferred"""

    def stopService(self):
        # shut down any pending actuation, and ensure that we wait for any
        # current actuation to complete by acquiring the lock.  This ensures
        # that no build will be scheduled after stopService is complete.
        d = self.actuationLock.acquire()
        def stop_actuating(_):
            self.actuateOk = False
            self.actuateAt = None
            if self.actuateAtTimer:
                self.actuateAtTimer.cancel()
            self.actuateAtTimer = None
        d.addCallback(stop_actuating)
        d.addCallback(lambda _ : self.actuationLock.release())

        # and chain to the parent class
        d.addCallback(lambda _ : base.BaseScheduler.stopService(self))
        return d

    ## Scheduler methods

    def getPendingBuildTimes(self):
        # take the latest-calculated value of actuateAt as a reasonable
        # estimate
        return [ self.actuateAt ]

    ## Timed methods

    def startBuild(self):
        """The time has come to start a new build.  Returns a Deferred.
        Override in subclasses."""
        raise NotImplementedError

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
        d = self.actuationLock.acquire()
        d.addCallback(lambda _ : self._scheduleNextBuild_locked())
        # always release the lock
        def release(x):
            self.actuationLock.release()
            return x
        d.addBoth(release)
        return d

    ## utilities

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
        def set_timer(actuateAt):
            now = self.now()
            self.actuateAt = max(actuateAt, now)
            if actuateAt is not None:
                untilNext = self.actuateAt - now
                if untilNext == 0:
                    log.msg(("%s: missed scheduled build time, so building "
                             "immediately") % self.name)
                self.actuateAtTimer = self._reactor.callLater(untilNext,
                                                              self._actuate)
        d.addCallback(set_timer)

        return d

    def _actuate(self):
        # called from the timer when it's time to start a build
        self.actuateAtTimer = None
        self.lastActuated = self.actuateAt

        d = self.actuationLock.acquire()

        @defer.deferredGenerator
        def set_state_and_start(_):
            # bail out if we shouldn't be actuating anymore
            if not self.actuateOk:
                return

            # mark the last build time
            self.actuateAt = None
            wfd = defer.waitForDeferred(self.setState('last_build',
                                                    self.lastActuated))
            yield wfd
            wfd.getResult()

            # start the build
            wfd = defer.waitForDeferred(self.startBuild())
            yield wfd
            wfd.getResult()

            # schedule the next build (noting the lock is already held)
            wfd = defer.waitForDeferred(self._scheduleNextBuild_locked())
            yield wfd
            wfd.getResult()
        d.addCallback(set_state_and_start)

        def unlock(x):
            self.actuationLock.release()
            return x
        d.addBoth(unlock)

        # this function can't return a deferred, so handle any failures via
        # log.err
        d.addErrback(log.err, 'while actuating')


class Periodic(Timed):
    compare_attrs = Timed.compare_attrs + ('periodicBuildTimer', 'branch',)

    def __init__(self, name, builderNames, periodicBuildTimer,
            branch=None, properties={}, onlyImportant=False):
        Timed.__init__(self, name=name, builderNames=builderNames,
                    properties=properties)
        assert periodicBuildTimer > 0, "periodicBuildTimer must be positive"
        self.periodicBuildTimer = periodicBuildTimer
        self.branch = branch
        self.reason = "The Periodic scheduler named '%s' triggered this build" % self.name

    def getNextBuildTime(self, lastActuated):
        if lastActuated is None:
            return defer.succeed(self.now()) # meaning "ASAP"
        else:
            return defer.succeed(lastActuated + self.periodicBuildTimer)

    def startBuild(self):
        return self.addBuildsetForLatest(reason=self.reason, branch=self.branch)

class NightlyBase(Timed):
    compare_attrs = (Timed.compare_attrs
            + ('minute', 'hour', 'dayOfMonth', 'month',
               'dayOfWeek', 'onlyIfChanged', 'fileIsImportant',
               'change_filter', 'onlyImportant',))

    def __init__(self, name, builderNames, minute=0, hour='*',
                 dayOfMonth='*', month='*', dayOfWeek='*',
                 properties={}):
        Timed.__init__(self, name=name, builderNames=builderNames, properties=properties)

        self.minute = minute
        self.hour = hour
        self.dayOfMonth = dayOfMonth
        self.month = month
        self.dayOfWeek = dayOfWeek

    def getNextBuildTime(self, lastActuated):
        def addTime(timetuple, secs):
            return time.localtime(time.mktime(timetuple)+secs)

        def check(ourvalue, value):
            if ourvalue == '*': return True
            if isinstance(ourvalue, int): return value == ourvalue
            return (value in ourvalue)

        dateTime = time.localtime(lastActuated or self.now())

        # Remove seconds by advancing to at least the next minute
        dateTime = addTime(dateTime, 60-dateTime[5])

        # Now we just keep adding minutes until we find something that matches
        # TODO: use a smarter algorithm, now that we have thorough tests

        yearLimit = dateTime[0]+2 # only check 2 years (a lot of minutes!)
        def isRunTime(timetuple):

            if not check(self.minute, timetuple[4]):
                return False

            if not check(self.hour, timetuple[3]):
                return False

            if not check(self.month, timetuple[1]):
                return False

            if self.dayOfMonth != '*' and self.dayOfWeek != '*':
                # They specified both day(s) of month AND day(s) of week.
                # This means that we only have to match one of the two. If
                # neither one matches, this time is not the right time.
                if not (check(self.dayOfMonth, timetuple[2]) or
                        check(self.dayOfWeek, timetuple[6])):
                    return False
            else:
                if not check(self.dayOfMonth, timetuple[2]):
                    return False

                if not check(self.dayOfWeek, timetuple[6]):
                    return False

            return True

        while not isRunTime(dateTime):
            dateTime = addTime(dateTime, 60)
            assert dateTime[0] < yearLimit, 'Something is wrong with this code'
        return defer.succeed(time.mktime(dateTime))

class Nightly(NightlyBase):
    compare_attrs = (NightlyBase.compare_attrs
            + ('onlyIfChanged', 'fileIsImportant', 'change_filter', 'onlyImportant',))

    class NoBranch: pass
    def __init__(self, name, builderNames, minute=0, hour='*',
                 dayOfMonth='*', month='*', dayOfWeek='*',
                 branch=NoBranch, fileIsImportant=None, onlyIfChanged=False,
                 properties={}, change_filter=None, onlyImportant=False):
        NightlyBase.__init__(self, name=name, builderNames=builderNames, minute=minute, hour='*',
                dayOfWeek=dayOfWeek, dayOfMonth=dayOfMonth, properties=properties)

        # If True, only important changes will be added to the buildset.
        self.onlyImportant = onlyImportant

        if fileIsImportant:
            assert callable(fileIsImportant), \
                "fileIsImportant must be a callable"
        assert branch is not Nightly.NoBranch, \
                "Nightly parameter 'branch' is required"

        self.branch = branch
        self.onlyIfChanged = onlyIfChanged
        self.fileIsImportant = fileIsImportant
        self.change_filter = filter.ChangeFilter.fromSchedulerConstructorArgs(
                change_filter=change_filter)
        self.reason = "The Nightly scheduler named '%s' triggered this build" % self.name

    def startTimedSchedulerService(self):
        if self.onlyIfChanged:
            return self.startConsumingChanges(fileIsImportant=self.fileIsImportant,
                                              change_filter=self.change_filter,
                                              onlyImportant=self.onlyImportant)
        else:
            return self.master.db.schedulers.flushChangeClassifications(self.schedulerid)

    def gotChange(self, change, important):
        # both important and unimportant changes on our branch are recorded, as
        # we will include all such changes in any buildsets we start.  Note
        # that we must check the branch here because it is not included in the
        # change filter
        if change.branch != self.branch:
            return defer.succeed(None) # don't care about this change
        return self.master.db.schedulers.classifyChanges(
                self.schedulerid, { change.number : important })

    @defer.deferredGenerator
    def startBuild(self):
        scheds = self.master.db.schedulers
        # if onlyIfChanged is True, then we will skip this build if no
        # important changes have occurred since the last invocation
        if self.onlyIfChanged:
            wfd = defer.waitForDeferred(scheds.getChangeClassifications(self.schedulerid))
            yield wfd
            classifications = wfd.getResult()

            # see if we have any important changes
            for imp in classifications.itervalues():
                if imp:
                    break
            else:
                log.msg(("Nightly Scheduler <%s>: skipping build " +
                         "- No important changes on configured branch") % self.name)
                return

            changeids = sorted(classifications.keys())
            wfd = defer.waitForDeferred(
                    self.addBuildsetForChanges(reason=self.reason, changeids=changeids))
            yield wfd
            wfd.getResult()

            max_changeid = changeids[-1] # (changeids are sorted)
            wfd = defer.waitForDeferred(
                    scheds.flushChangeClassifications(self.schedulerid,
                                                      less_than=max_changeid+1))
            yield wfd
            wfd.getResult()
        else:
            # start a build of the latest revision, whatever that is
            wfd = defer.waitForDeferred(
                    self.addBuildsetForLatest(reason=self.reason, branch=self.branch))
            yield wfd
            wfd.getResult()

class NightlyTriggerable(NightlyBase):
    implements(ITriggerableScheduler)
    def __init__(self, name, builderNames, minute=0, hour='*',
                 dayOfMonth='*', month='*', dayOfWeek='*',
                 properties={}):
        NightlyBase.__init__(self, name=name, builderNames=builderNames, minute=minute, hour='*',
                dayOfWeek=dayOfWeek, dayOfMonth=dayOfMonth, properties=properties)

        self._lastTrigger = None
        self.reason = "The NightlyTriggerable scheduler named '%s' triggered this build" % self.name

    def startService(self):
        NightlyBase.startService(self)

        # get the scheduler's lastTrigger time (note: only done at startup)
        d = self.getState('lastTrigger', None)
        def setLast(lastTrigger):
            if lastTrigger:
                self._lastTrigger = (lastTrigger[0], properties.Properties.fromDict(lastTrigger[1]))
        d.addCallback(setLast)

    def trigger(self, ssid, set_props=None):
        """Trigger this scheduler with the given sourcestamp ID. Returns a
        deferred that will fire when the buildset is finished."""
        self._lastTrigger = (ssid, set_props)

        # record the trigger in the db
        if set_props:
            propsDict = set_props.asDict()
        else:
            propsDict = {}
        d = self.setState('lastTrigger',
                (ssid, propsDict))

        ## FIXME: Trigger expects a callback with the success of the triggered
        ## build, if waitForFinish is True. That probably isn't important here,
        ## so just return SUCCESS for now.
        return d.addCallback(lambda _: buildstep.SUCCESS)

    @defer.inlineCallbacks
    def startBuild(self):
        if self._lastTrigger is None:
            defer.returnValue(None)

        (ssid, set_props) = self._lastTrigger
        self._lastTrigger = None
        yield self.setState('lastTrigger', None)

        ## TODO: The following code is copied from Triggerable.trigger

        # properties for this buildset are composed of our own properties,
        # potentially overridden by anything from the triggering build
        props = properties.Properties()
        props.updateFromProperties(self.properties)
        if set_props:
            props.updateFromProperties(set_props)

        if ssid:
            yield self.addBuildsetForSourceStamp(reason=self.reason, ssid=ssid,
                    properties=props)
        else:
            yield self.addBuildsetForLatest(reason=self.reason, properties=props)
