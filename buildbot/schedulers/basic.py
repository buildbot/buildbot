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
from zope.interface import implements
from twisted.application import service

from buildbot import interfaces
from buildbot.process.properties import Properties
from buildbot.util import defaultdict, ComparableMixin
from buildbot.sourcestamp import SourceStamp
from buildbot.status.builder import SUCCESS, WARNINGS

class _None:
    pass

class _Base(service.MultiService, ComparableMixin):
    implements(interfaces.IScheduler)
    # subclasses must set .compare_attrs

    upstream_name = None # set to be notified about upstream buildsets

    def __init__(self, name, builderNames, properties, categories):
        service.MultiService.__init__(self)
        self.name = name
        self.properties = Properties()
        self.properties.update(properties, "Scheduler")
        self.properties.setProperty("scheduler", name, "Scheduler")
        errmsg = ("The builderNames= argument to Scheduler must be a list "
                  "of Builder description names (i.e. the 'name' key of the "
                  "Builder specification dictionary)")
        assert isinstance(builderNames, (list, tuple)), errmsg
        for b in builderNames:
            assert isinstance(b, str), errmsg
        self.builderNames = builderNames
        self.categories = categories
        # I will acquire a .schedulerid value before I'm started

    def compareToOther(self, them):
        # like ComparableMixin.__cmp__, but only used by our manager
        result = cmp(type(self), type(them))
        if result:
            return result
        result = cmp(self.__class__, them.__class__)
        if result:
            return result
        assert self.compare_attrs == them.compare_attrs
        self_list = [getattr(self, name, _None) for name in self.compare_attrs]
        them_list = [getattr(them, name, _None) for name in self.compare_attrs]
        return cmp(self_list, them_list)

    def get_initial_state(self, max_changeid):
        # override this if you pay attention to Changes, probably to:
        #return {"last_processed": max_changeid}
        return {}

    def get_state(self, t):
        return self.parent.db.scheduler_get_state(self.schedulerid, t)
    def set_state(self, t, state):
        self.parent.db.scheduler_set_state(self.schedulerid, t, state)

    def listBuilderNames(self):
        return self.builderNames

    def create_buildset(self, ssid, reason, t, props=_None, builderNames=None):
        db = self.parent.db
        if props is _None:
            props = self.properties
        if builderNames is None:
            builderNames = self.builderNames
        bsid = db.create_buildset(ssid, reason, props, builderNames, t)
        # notify downstream schedulers so they can watch for it to complete
        self.parent.publish_buildset(self.name, bsid, t)
        return bsid

class ClassifierMixin:

    def classify_changes(self, t):
        db = self.parent.db
        cm = self.parent.change_svc
        state = self.get_state(t)
        last_processed = state["last_processed"]

        changes = cm.getChangesGreaterThan(last_processed, t)
        for c in changes:
            if self.changeIsRelevant(c):
                important = True
                if self.fileIsImportant:
                    important = self.fileIsImportant(c)
                db.scheduler_classify_change(self.schedulerid, c.number,
                                             bool(important), t)
        # now that we've recorded a decision about each, we can update the
        # last_processed record
        if changes:
            max_changeid = max([c.number for c in changes])
            state["last_processed"] = max_changeid # retain other keys
            self.set_state(t, state)

class Scheduler(_Base, ClassifierMixin):
    fileIsImportant = None
    compare_attrs = ('name', 'treeStableTimer', 'builderNames', 'branch',
                     'fileIsImportant', 'properties', 'categories')

    def __init__(self, name, branch, treeStableTimer, builderNames,
                 fileIsImportant=None, properties={}, categories=None):
        """
        @param name: the name of this Scheduler
        @param branch: The branch name that the Scheduler should pay
                       attention to. Any Change that is not in this branch
                       will be ignored. It can be set to None to only pay
                       attention to the default branch.
        @param treeStableTimer: the duration, in seconds, for which the tree
                                must remain unchanged before a build is
                                triggered. This is intended to avoid builds
                                of partially-committed fixes. If None, then
                                a separate build will be made for each
                                Change, regardless of when they arrive.
        @param builderNames: a list of Builder names. When this Scheduler
                             decides to start a set of builds, they will be
                             run on the Builders named by this list.

        @param fileIsImportant: A callable which takes one argument (a Change
                                instance) and returns True if the change is
                                worth building, and False if it is not.
                                Unimportant Changes are accumulated until the
                                build is triggered by an important change.
                                The default value of None means that all
                                Changes are important.

        @param properties: properties to apply to all builds started from
                           this scheduler
        @param categories: A list of categories of changes to accept
        """

        _Base.__init__(self, name, builderNames, properties, categories)
        self.treeStableTimer = treeStableTimer
        self.branch = branch
        if fileIsImportant:
            assert callable(fileIsImportant)
            self.fileIsImportant = fileIsImportant

    def get_initial_state(self, max_changeid):
        return {"last_processed": max_changeid}

    def getPendingBuildTimes(self):
        return []

    def changeIsRelevant(self, change):
        if change.branch != self.branch:
            return False
        if self.categories is not None:
            if change.category not in self.categories:
                return False
        return True

    def run(self):
        db = self.parent.db
        d = db.runInteraction(self.classify_changes)
        d.addCallback(lambda ign: db.runInteraction(self._process_changes))
        return d

    def _process_changes(self, t):
        db = self.parent.db
        res = db.scheduler_get_classified_changes(self.schedulerid, t)
        (important, unimportant) = res
        return self.decide_and_remove_changes(t, important, unimportant)

    def decide_and_remove_changes(self, t, important, unimportant):
        """Look at the changes that need to be processed and decide whether
        to queue a BuildRequest or sleep until something changes.

        If I decide that a build should be performed, I will add the
        appropriate BuildRequest to the database queue, and remove the
        (retired) changes that went into it from the scheduler_changes tabke.

        Returns wakeup_delay: either None, or a float indicating when this
        scheduler wants to be woken up next. The Scheduler is responsible for
        padding its desired wakeup time by about a second to avoid frenetic
        must-wake-up-at-exactly-8AM behavior. The Loop may silently impose a
        minimum delay request of a couple seconds to prevent this sort of
        thing, but Schedulers must still add their own padding to avoid at
        least a double wakeup.
        """

        if not important:
            return None
        all_changes = important + unimportant
        most_recent = max([c.when for c in all_changes])
        if self.treeStableTimer is not None:
            now = time.time()
            stable_at = most_recent + self.treeStableTimer
            if stable_at > now:
                # Wake up one second late, to avoid waking up too early and
                # looping a lot.
                return stable_at + 1.0

        # ok, do a build
        self._add_build_and_remove_changes(t, all_changes)
        return None

    def _add_build_and_remove_changes(self, t, all_changes):
        db = self.parent.db
        if self.treeStableTimer is None:
            # each Change gets a separate build
            for c in all_changes:
                ss = SourceStamp(changes=[c])
                ssid = db.get_sourcestampid(ss, t)
                self.create_buildset(ssid, "scheduler", t)
        else:
            ss = SourceStamp(changes=all_changes)
            ssid = db.get_sourcestampid(ss, t)
            self.create_buildset(ssid, "scheduler", t)

        # and finally retire the changes from scheduler_changes
        changeids = [c.number for c in all_changes]
        db.scheduler_retire_changes(self.schedulerid, changeids, t)


class AnyBranchScheduler(Scheduler):
    compare_attrs = ('name', 'treeStableTimer', 'builderNames',
                     'fileIsImportant', 'properties', 'categories')
    def __init__(self, name, treeStableTimer, builderNames,
                 fileIsImportant=None, properties={}, categories=None):
        """
        @param name: the name of this Scheduler
        @param treeStableTimer: the duration, in seconds, for which the tree
                                must remain unchanged before a build is
                                triggered. This is intended to avoid builds
                                of partially-committed fixes.
        @param builderNames: a list of Builder names. When this Scheduler
                             decides to start a set of builds, they will be
                             run on the Builders named by this list.

        @param fileIsImportant: A callable which takes one argument (a Change
                                instance) and returns True if the change is
                                worth building, and False if it is not.
                                Unimportant Changes are accumulated until the
                                build is triggered by an important change.
                                The default value of None means that all
                                Changes are important.

        @param properties: properties to apply to all builds started from
                           this scheduler
        @param categories: A list of categories of changes to accept
        """

        _Base.__init__(self, name, builderNames, properties, categories)
        self.treeStableTimer = treeStableTimer
        if fileIsImportant:
            assert callable(fileIsImportant)
            self.fileIsImportant = fileIsImportant

    def changeIsRelevant(self, change):
        if self.categories is not None:
            if change.category not in self.categories:
                return False
        return True

    def _process_changes(self, t):
        db = self.parent.db
        res = db.scheduler_get_classified_changes(self.schedulerid, t)
        (important, unimportant) = res
        def _twolists(): return [], [] # important, unimportant
        branch_changes = defaultdict(_twolists)
        for c in important:
            branch_changes[c.branch][0].append(c)
        for c in unimportant:
            branch_changes[c.branch][1].append(c)
        delays = []
        for branch in branch_changes:
            (b_important, b_unimportant) = branch_changes[branch]
            delay = self.decide_and_remove_changes(t, b_important,
                                                   b_unimportant)
            if delay is not None:
                delays.append(delay)
        if delays:
            return min(delays)
        return None

class Dependent(_Base):
    # register with our upstream, so they'll tell us when they submit a
    # buildset
    compare_attrs = ('name', 'upstream_name', 'builderNames', 'properties',
                     'categories')

    def __init__(self, name, upstream, builderNames,
                 properties={}, categories=None):
        assert interfaces.IScheduler.providedBy(upstream)
        _Base.__init__(self, name, builderNames, properties, categories)
        # by setting self.upstream_name, our buildSetSubmitted() method will
        # be called whenever that upstream Scheduler adds a buildset to the
        # DB.
        self.upstream_name = upstream.name

    def getPendingBuildTimes(self):
        return []

    def buildSetSubmitted(self, bsid, t):
        db = self.parent.db
        db.scheduler_subscribe_to_buildset(self.schedulerid, bsid, t)

    def run(self):
        d = self.parent.db.runInteraction(self._run)
        return d
    def _run(self, t):
        db = self.parent.db
        res = db.scheduler_get_subscribed_buildsets(self.schedulerid, t)
        # this returns bsid,ssid,results for all of our active subscriptions.
        # We ignore the ones that aren't complete yet. This leaves the
        # subscription in place until the buildset is complete.
        for (bsid,ssid,complete,results) in res:
            if complete:
                if results in (SUCCESS, WARNINGS):
                    self.create_buildset(ssid, "downstream", t)
                db.scheduler_unsubscribe_buildset(self.schedulerid, bsid, t)
        return None

# Dependent/Triggerable schedulers will make a BuildSet with linked
# BuildRequests. The rest (which don't generally care when the set
# finishes) will just make the BuildRequests.

# runInteraction() should give us the all-or-nothing transaction
# semantics we want, with synchronous operation during the
# interaction function, transactions fail instead of retrying. So if
# a concurrent actor touches the database in a way that blocks the
# transaction, we'll get an errback. That will cause the overall
# Scheduler to errback, and not commit its "all Changes before X have
# been handled" update. The next time that Scheduler is processed, it
# should try everything again.
