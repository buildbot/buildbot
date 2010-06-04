# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla-specific Buildbot steps.
#
# The Initial Developer of the Original Code is
# Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Brian Warner <warner@lothar.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

import time
from twisted.internet import defer
from twisted.python import log
from buildbot.sourcestamp import SourceStamp
from buildbot.schedulers import base

class TimedBuildMixin:

    def start_HEAD_build(self, t):
        # start a build (of the tip of self.branch)
        db = self.parent.db
        ss = SourceStamp(branch=self.branch)
        ssid = db.get_sourcestampid(ss, t)
        self.create_buildset(ssid, self.reason, t)

    def start_requested_build(self, t, relevant_changes):
        # start a build with the requested list of changes on self.branch
        db = self.parent.db
        ss = SourceStamp(branch=self.branch, changes=relevant_changes)
        ssid = db.get_sourcestampid(ss, t)
        self.create_buildset(ssid, self.reason, t)

    def update_last_build(self, t, when):
        # and record when we did it
        state = self.get_state(t)
        state["last_build"] = when
        self.set_state(t, state)

class Periodic(base.BaseScheduler, TimedBuildMixin):
    """Instead of watching for Changes, this Scheduler can just start a build
    at fixed intervals. The C{periodicBuildTimer} parameter sets the number
    of seconds to wait between such periodic builds. The first build will be
    run immediately."""

    # TODO: consider having this watch another (changed-based) scheduler and
    # merely enforce a minimum time between builds.
    compare_attrs = ('name', 'builderNames', 'periodicBuildTimer', 'branch',
                     'properties')

    def __init__(self, name, builderNames, periodicBuildTimer,
            branch=None, properties={}):
        base.BaseScheduler.__init__(self, name, builderNames, properties)
        self.periodicBuildTimer = periodicBuildTimer
        self.branch = branch
        self.reason = ("The Periodic scheduler named '%s' triggered this build"
                       % name)

    def get_initial_state(self, max_changeid):
        return {"last_build": None}

    def getPendingBuildTimes(self):
        db = self.parent.db
        s = db.runInteractionNow(self.get_state)
        last_build = s["last_build"]
        now = time.time()
        if last_build is None:
            return [now]
        return [last_build + self.periodicBuildTimer]

    def run(self):
        db = self.parent.db
        d = db.runInteraction(self._run)
        return d

    def _run(self, t):
        now = time.time()
        s = self.get_state(t)
        last_build = s["last_build"]
        if last_build is None:
            self.start_HEAD_build(t)
            self.update_last_build(t, now)
            last_build = now
        when = last_build + self.periodicBuildTimer
        if when < now:
            self.start_HEAD_build(t)
            self.update_last_build(t, now)
            last_build = now
            when = now + self.periodicBuildTimer
        return when + 1.0


class Nightly(base.BaseScheduler, base.ClassifierMixin, TimedBuildMixin):
    """Imitate 'cron' scheduling. This can be used to schedule a nightly
    build, or one which runs are certain times of the day, week, or month.

    Pass some subset of minute, hour, dayOfMonth, month, and dayOfWeek; each
    may be a single number or a list of valid values. The builds will be
    triggered whenever the current time matches these values. Wildcards are
    represented by a '*' string. All fields default to a wildcard except
    'minute', so with no fields this defaults to a build every hour, on the
    hour.

    For example, the following master.cfg clause will cause a build to be
    started every night at 3:00am::

     s = Nightly(name='nightly', builderNames=['builder1', 'builder2'],
                 hour=3, minute=0)
     c['schedules'].append(s)

    This scheduler will perform a build each monday morning at 6:23am and
    again at 8:23am::

     s = Nightly(name='BeforeWork', builderNames=['builder1'],
                 dayOfWeek=0, hour=[6,8], minute=23)

    The following runs a build every two hours::

     s = Nightly(name='every2hours', builderNames=['builder1'],
                 hour=range(0, 24, 2))

    And this one will run only on December 24th::

     s = Nightly(name='SleighPreflightCheck',
                 builderNames=['flying_circuits', 'radar'],
                 month=12, dayOfMonth=24, hour=12, minute=0)

    For dayOfWeek and dayOfMonth, builds are triggered if the date matches
    either of them. All time values are compared against the tuple returned
    by time.localtime(), so month and dayOfMonth numbers start at 1, not
    zero. dayOfWeek=0 is Monday, dayOfWeek=6 is Sunday.

    When onlyIfChanged is True, the build is triggered only if changes have
    arrived on the given branch since the last build was performed. As a
    further restriction, if fileIsImportant= is provided (a one-argument
    callable which takes a Change object and returns a bool), then the build
    will be triggered only if at least one of those changes qualifies as
    'important'. The following example will run a build at 3am, but only when
    a source code file (.c/.h) has been changed:

     def isSourceFile(change):
         for fn in change.files:
             if fn.endswith('.c') or fn.endswith('.h'):
                 return True
         return False
     s = Nightly(name='nightly-when-changed', builderNames=['builder1'],
                 hour=3, minute=0,
                 onlyIfChanged=True, fileIsImportant=isSourceFile)

    onlyIfChanged defaults to False, which means a build will be performed
    even if nothing has changed.
    """

    compare_attrs = ('name', 'builderNames',
                     'minute', 'hour', 'dayOfMonth', 'month',
                     'dayOfWeek', 'branch', 'onlyIfChanged',
                     'fileIsImportant', 'properties')

    def __init__(self, name, builderNames, minute=0, hour='*',
                 dayOfMonth='*', month='*', dayOfWeek='*',
                 branch=None, fileIsImportant=None, onlyIfChanged=False,
                 properties={}):
        # Setting minute=0 really makes this an 'Hourly' scheduler. This
        # seemed like a better default than minute='*', which would result in
        # a build every 60 seconds.
        base.BaseScheduler.__init__(self, name, builderNames, properties)
        self.minute = minute
        self.hour = hour
        self.dayOfMonth = dayOfMonth
        self.month = month
        self.dayOfWeek = dayOfWeek
        self.branch = branch
        self.onlyIfChanged = onlyIfChanged
        self.delayedRun = None
        self.nextRunTime = None
        self.reason = ("The Nightly scheduler named '%s' triggered this build"
                       % name)
        self.fileIsImportant = None
        if fileIsImportant:
            assert callable(fileIsImportant)
            self.fileIsImportant = fileIsImportant
        self._start_time = time.time()

        # this scheduler does not support filtering, but ClassifierMixin needs a
        # filter anyway
        self.make_filter()

    def get_initial_state(self, max_changeid):
        return {
            "last_build": None,
            "last_processed": max_changeid,
        }

    def getPendingBuildTimes(self):
        now = time.time()
        next = self._calculateNextRunTimeFrom(now)
        # note: this ignores onlyIfChanged
        return [next]

    def run(self):
        d = defer.succeed(None)
        db = self.parent.db
        # always call classify_changes, so that we can keep last_processed
        # up to date, in case we are configured with onlyIfChanged.
        d.addCallback(lambda ign: db.runInteraction(self.classify_changes))
        d.addCallback(lambda ign: db.runInteraction(self._check_timer))
        return d

    def _check_timer(self, t):
        now = time.time()
        s = self.get_state(t)
        last_build = s["last_build"]
        if last_build is None:
            next = self._calculateNextRunTimeFrom(self._start_time)
        else:
            next = self._calculateNextRunTimeFrom(last_build)

        # not ready to fire yet
        if next >= now:
            return next + 1.0

        self._maybe_start_build(t)
        self.update_last_build(t, now)

        # reschedule for the next timer
        return self._check_timer(t)

    def _maybe_start_build(self, t):
        if self.onlyIfChanged:
            db = self.parent.db
            res = db.scheduler_get_classified_changes(self.schedulerid, t)
            (important, unimportant) = res
            if not important:
                log.msg("Nightly Scheduler <%s>: "
                        "skipping build - No important change" % self.name)
                return
            relevant_changes = [c for c in (important + unimportant) if
                                c.branch == self.branch]
            if not relevant_changes:
                log.msg("Nightly Scheduler <%s>: "
                        "skipping build - No relevant change on branch" %
                        self.name)
                return
            self.start_requested_build(t, relevant_changes)
            # retire the changes
            changeids = [c.number for c in relevant_changes]
            db.scheduler_retire_changes(self.schedulerid, changeids, t)
        else:
            # start it unconditionally
            self.start_HEAD_build(t)

    def _addTime(self, timetuple, secs):
        return time.localtime(time.mktime(timetuple)+secs)

    def _isRunTime(self, timetuple):
        def check(ourvalue, value):
            if ourvalue == '*': return True
            if isinstance(ourvalue, int): return value == ourvalue
            return (value in ourvalue)

        if not check(self.minute, timetuple[4]):
            #print 'bad minute', timetuple[4], self.minute
            return False

        if not check(self.hour, timetuple[3]):
            #print 'bad hour', timetuple[3], self.hour
            return False

        if not check(self.month, timetuple[1]):
            #print 'bad month', timetuple[1], self.month
            return False

        if self.dayOfMonth != '*' and self.dayOfWeek != '*':
            # They specified both day(s) of month AND day(s) of week.
            # This means that we only have to match one of the two. If
            # neither one matches, this time is not the right time.
            if not (check(self.dayOfMonth, timetuple[2]) or
                    check(self.dayOfWeek, timetuple[6])):
                #print 'bad day'
                return False
        else:
            if not check(self.dayOfMonth, timetuple[2]):
                #print 'bad day of month'
                return False

            if not check(self.dayOfWeek, timetuple[6]):
                #print 'bad day of week'
                return False

        return True

    def _calculateNextRunTimeFrom(self, now):
        dateTime = time.localtime(now)

        # Remove seconds by advancing to at least the next minute
        dateTime = self._addTime(dateTime, 60-dateTime[5])

        # Now we just keep adding minutes until we find something that matches

        # It not an efficient algorithm, but it'll *work* for now
        yearLimit = dateTime[0]+2
        while not self._isRunTime(dateTime):
            dateTime = self._addTime(dateTime, 60)
            #print 'Trying', time.asctime(dateTime)
            assert dateTime[0] < yearLimit, 'Something is wrong with this code'
        return time.mktime(dateTime)
