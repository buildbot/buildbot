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
from buildbot import util
from buildbot.changes import changes
from buildbot.changes import filter
from buildbot.schedulers import base
from buildbot.schedulers import dependent
from buildbot.util import NotABranch
from collections import defaultdict
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log


class BaseBasicScheduler(base.BaseScheduler):

    """
    @param onlyImportant: If True, only important changes will be added to the
                          buildset.
    @type onlyImportant: boolean

    """

    compare_attrs = ['treeStableTimer', 'change_filter', 'fileIsImportant',
                     'onlyImportant', 'reason', 'coolDownTimer']

    _reactor = reactor  # for tests

    fileIsImportant = None
    reason = ''

    class NotSet:
        pass

    def __init__(self, name, shouldntBeSet=NotSet, 
                 treeStableTimer=None, coolDownTimer=None,
                 builderNames=None, branch=NotABranch, branches=NotABranch,
                 fileIsImportant=None, properties={}, categories=None,
                 reason="The %(classname)s scheduler named '%(name)s' triggered this build",
                 change_filter=None, onlyImportant=False, **kwargs):
        if shouldntBeSet is not self.NotSet:
            config.error(
                "pass arguments to schedulers using keyword arguments")
        if fileIsImportant and not callable(fileIsImportant):
            config.error(
                "fileIsImportant must be a callable")

        # initialize parent classes
        base.BaseScheduler.__init__(self, name, builderNames, properties, **kwargs)

        self.treeStableTimer = treeStableTimer
        self.coolDownTimer = coolDownTimer
        if fileIsImportant is not None:
            self.fileIsImportant = fileIsImportant
        self.onlyImportant = onlyImportant
        self.change_filter = self.getChangeFilter(branch=branch,
                                                  branches=branches, change_filter=change_filter,
                                                  categories=categories)

        # the IDelayedCall used to wake up when this scheduler's
        # treeStableTimer expires.
        self._stable_timers = {}
        self._cooldown_timers = {}
        self._timers_lock = defer.DeferredLock()

        self.reason = reason % {'name': name, 'classname': self.__class__.__name__}

    def getChangeFilter(self, branch, branches, change_filter, categories):
        raise NotImplementedError

    def preStartConsumingChanges(self):
        # Hook for subclasses to setup before startConsumingChanges().
        return defer.succeed(None)

    def startService(self, _returnDeferred=False):
        base.BaseScheduler.startService(self)

        d = self.preStartConsumingChanges()

        d.addCallback(lambda _:
                      self.startConsumingChanges(fileIsImportant=self.fileIsImportant,
                                                 change_filter=self.change_filter,
                                                 onlyImportant=self.onlyImportant))

        # We only care about classified changes if we have a timer to consider.
        # If not, get rid of any hanging around from previous configurations
        if not self.treeStableTimer and not self.coolDownTimer:
            d.addCallback(lambda _:
                          self.master.db.schedulers.flushChangeClassifications(
                              self.objectid))

        # otherwise, if there are classified changes out there, start their
        # treeStableTimers again
        else:
            d.addCallback(lambda _:
                          self.scanExistingClassifiedChanges())

        # handle Deferred errors, since startService does not return a Deferred
        d.addErrback(log.err, "while starting SingleBranchScheduler '%s'"
                              % self.name)

        if _returnDeferred:
            return d  # only used in tests

    def stopService(self):
        # the base stopService will unsubscribe from new changes
        d = base.BaseScheduler.stopService(self)

        @util.deferredLocked(self._timers_lock)
        def cancel_timers(_):
            for timer in self._stable_timers.values():
                timer.cancel()
            for timer in self._cooldown_timers.values():
                timer['timer'].cancel()
            self._stable_timers.clear()
            self._cooldown_timers.clear()
        d.addCallback(cancel_timers)
        return d

    @util.deferredLocked('_timers_lock')
    @defer.inlineCallbacks
    def gotChange(self, change, important):
        if not self.treeStableTimer and not self.coolDownTimer:
            # If there's no timers, we can completely ignore
            # unimportant changes
            if not important:
                defer.returnValue(None)
            # otherwise, we'll build it right away
            yield self.addBuildsetForChanges(reason=self.reason,
                                             changeids=[change.number])
            defer.returnValue(None)

        timer_name = self.getTimerNameForChange(change)

        # Mark the cooldown timer as blocking something.
        if self.coolDownTimer and timer_name in self._cooldown_timers:
            self._cooldown_timers[timer_name]['pending'] = True

        # Persist the change. Since stable/cooldown timers are active,
        # we may need to revisit it later.
        yield self.master.db.schedulers.classifyChanges(
                 self.objectid, {change.number: important})

        # Tree-stable timer:
        # - for an important change, start the timer
        # - for an unimportant change, reset the timer if it is running
        if self.treeStableTimer:
            old_stable_timer = self._stable_timers.get(timer_name)
            if not important and not old_stable_timer:
                defer.returnValue(None)

            if old_stable_timer:
                old_stable_timer.cancel()

            def fire_timer():
                d = self._timerFired(timer_name, self._stable_timers)
                d.addErrback(log.err, "while firing stable timer")

            self._stable_timers[timer_name] = self._reactor.callLater(
                self.treeStableTimer, fire_timer)
        else:
            yield self.handleExpiredTimers(timer_name)

    @defer.inlineCallbacks
    def scanExistingClassifiedChanges(self):
        # call gotChange for each classified change.  This is called at startup
        # and is intended to re-start the treeStableTimer for any changes that
        # had not yet been built when the scheduler was stopped.

        # NOTE: this may double-call gotChange for changes that arrive just as
        # the scheduler starts up.  In practice, this doesn't hurt anything.
        classifications = \
            yield self.master.db.schedulers.getChangeClassifications(
                self.objectid)

        # call gotChange for each change, after first fetching it from the db
        for changeid, important in classifications.iteritems():
            chdict = yield self.master.db.changes.getChange(changeid)

            if not chdict:
                continue

            change = yield changes.Change.fromChdict(self.master, chdict)
            yield self.gotChange(change, important)

    def getTimerNameForChange(self, change):
        raise NotImplementedError  # see subclasses

    def getChangeClassificationsForTimer(self, objectid, timer_name):
        """similar to db.schedulers.getChangeClassifications, but given timer
        name"""
        raise NotImplementedError  # see subclasses

    @util.deferredLocked('_timers_lock')
    @defer.inlineCallbacks
    def _timerFired(self, timer_name, timers_dict):
        # The service may haev been stopped, so just bail out
        if timer_name not in timers_dict:
            return

        # Delete this now-fired timer.
        del timers_dict[timer_name]

        yield self.handleExpiredTimers(timer_name)

    @defer.inlineCallbacks
    def handleExpiredTimers(self, timer_name):
        # If either timer is still pending, we have to wait.
        if timer_name in self._stable_timers:
            return
        if timer_name in self._cooldown_timers:
            return

        classifications = \
            yield self.getChangeClassificationsForTimer(self.objectid,
                                                        timer_name)

        # just in case: databases do weird things sometimes!
        if not classifications:  # pragma: no cover
            return

        # Start cool-down timer to hold off future changes.
        if self.coolDownTimer:
            def fire_timer():
                d = self._timerFired(timer_name, self._cooldown_timers)
                d.addErrback(log.err, "while firing cooldown timer")

            d = self._reactor.callLater(self.coolDownTimer, fire_timer)
            self._cooldown_timers[timer_name] = dict(timer=d, pending=False)

        changeids = sorted(classifications.keys())
        yield self.addBuildsetForChanges(reason=self.reason,
                                         changeids=changeids)

        max_changeid = changeids[-1]  # (changeids are sorted)
        yield self.master.db.schedulers.flushChangeClassifications(
            self.objectid, less_than=max_changeid + 1)

    def getPendingBuildTimes(self):
        # This isn't locked, since the caller expects an immediate value,
        # and in any case, this is only an estimate.

        timer_names = set(self._stable_timers.keys() + self._cooldown_timers.keys())
        ret = []
        for timer_name in timer_names:
            times = []

            stable_timer = self._stable_timers.get(timer_name)
            if stable_timer and stable_timer.active():
                times.append(stable_timer.getTime())

            cooldown_timer = self._cooldown_timers.get(timer_name)
            if cooldown_timer and cooldown_timer['timer'].active():
                # This timer only counts if it's blocking changes.
                # We use a cheap bool flag for that test.
                if cooldown_timer['pending']:
                    times.append(cooldown_timer['timer'].getTime())

            # Each classification fires after all timers are done. 
            if times:
                ret.append(max(times))

        return ret


class SingleBranchScheduler(BaseBasicScheduler):

    def __init__(self, name, createAbsoluteSourceStamps=False, **kwargs):
        self._lastCodebases = {}
        self.createAbsoluteSourceStamps = createAbsoluteSourceStamps
        BaseBasicScheduler.__init__(self, name, **kwargs)

    def preStartConsumingChanges(self):
        if self.createAbsoluteSourceStamps:
            # load saved codebases
            d = self.getState("lastCodebases", {})

            def setLast(lastCodebases):
                self._lastCodebases = lastCodebases
            d.addCallback(setLast)
            return d
        else:
            return defer.succeed(None)

    def gotChange(self, change, important):
        d = defer.succeed(None)

        if self.createAbsoluteSourceStamps:
            self._lastCodebases.setdefault(change.codebase, {})
            lastChange = self._lastCodebases[change.codebase].get('lastChange', -1)

            codebaseDict = dict(repository=change.repository,
                                branch=change.branch,
                                revision=change.revision,
                                lastChange=change.number)

            if change.number > lastChange:
                self._lastCodebases[change.codebase] = codebaseDict
                d.addCallback(lambda _:
                              self.setState('lastCodebases', self._lastCodebases))

        d.addCallback(lambda _:
                      BaseBasicScheduler.gotChange(self, change, important))
        return d

    def getCodebaseDict(self, codebase):
        if self.createAbsoluteSourceStamps:
            return self._lastCodebases.get(codebase, self.codebases[codebase])
        else:
            return self.codebases[codebase]

    def getChangeFilter(self, branch, branches, change_filter, categories):
        if branch is NotABranch and not change_filter:
            config.error(
                "the 'branch' argument to SingleBranchScheduler is " +
                "mandatory unless change_filter is provided")
        elif branches is not NotABranch:
            config.error(
                "the 'branches' argument is not allowed for " +
                "SingleBranchScheduler")

        return filter.ChangeFilter.fromSchedulerConstructorArgs(
            change_filter=change_filter, branch=branch,
            categories=categories)

    def getTimerNameForChange(self, change):
        return "only"  # this class only uses one timer

    def getChangeClassificationsForTimer(self, objectid, timer_name):
        return self.master.db.schedulers.getChangeClassifications(
            self.objectid)


class Scheduler(SingleBranchScheduler):

    "alias for SingleBranchScheduler"

    def __init__(self, *args, **kwargs):
        log.msg("WARNING: the name 'Scheduler' is deprecated; use " +
                "buildbot.schedulers.basic.SingleBranchScheduler instead " +
                "(note that this may require you to change your import " +
                "statement)")
        SingleBranchScheduler.__init__(self, *args, **kwargs)


class AnyBranchScheduler(BaseBasicScheduler):

    def getChangeFilter(self, branch, branches, change_filter, categories):
        assert branch is NotABranch
        return filter.ChangeFilter.fromSchedulerConstructorArgs(
            change_filter=change_filter, branch=branches,
            categories=categories)

    def getTimerNameForChange(self, change):
        # Py2.6+: could be a namedtuple
        return (change.codebase, change.project, change.repository, change.branch)

    def getChangeClassificationsForTimer(self, objectid, timer_name):
        codebase, project, repository, branch = timer_name  # set in getTimerNameForChange
        return self.master.db.schedulers.getChangeClassifications(
            self.objectid, branch=branch, repository=repository,
            codebase=codebase, project=project)

# now at buildbot.schedulers.dependent, but keep the old name alive
Dependent = dependent.Dependent
