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

from zope.interface import implements
from twisted.application import service

from buildbot import interfaces
from buildbot.process.properties import Properties
from buildbot.util import ComparableMixin, NotABranch
from buildbot.schedulers import filter

class _None:
    pass

class BaseScheduler(service.MultiService, ComparableMixin):
    implements(interfaces.IScheduler)
    # subclasses must set .compare_attrs

    upstream_name = None # set to be notified about upstream buildsets

    def __init__(self, name, builderNames, properties):
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
        # I will acquire a .schedulerid value before I'm started

    def compareToOther(self, them):
        # like ComparableMixin.__cmp__, but only used by our manager
        # TODO: why?? why not use __cmp__?
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

    def getPendingBuildTimes(self):
        return []

    def create_buildset(self, ssid, reason, t, props=None, builderNames=None):
        db = self.parent.db
        if props is None:
            props = self.properties
        if builderNames is None:
            builderNames = self.builderNames
        bsid = db.create_buildset(ssid, reason, props, builderNames, t)
        # notify downstream schedulers so they can watch for it to complete
        self.parent.publish_buildset(self.name, bsid, t)
        return bsid

class ClassifierMixin:
    """
    Mixin to classify changes using self.change_filter, a filter.ChangeFilter instance.
    """

    def make_filter(self, change_filter=None, branch=NotABranch, categories=None):
        if change_filter:
            if (branch is not NotABranch or categories is not None):
                raise RuntimeError("cannot specify both change_filter and either branch or categories")
            self.change_filter = change_filter
            return

        # build a change filter from the deprecated category and branch args
        cfargs = {}
        if branch is not NotABranch: cfargs['branch'] = branch
        if categories: cfargs['category'] = categories
        self.change_filter = filter.ChangeFilter(**cfargs)

    def classify_changes(self, t):
        db = self.parent.db
        state = self.get_state(t)
        state_changed = False
        last_processed = state.get("last_processed", None)

        if last_processed is None:
            last_processed = state['last_processed'] = db.getLatestChangeid() # TODO: may not work in a transaction..
            state_changed = True

        changes = db.getChangesGreaterThan(last_processed, t)
        for c in changes:
            if self.change_filter.filter_change(c):
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
            state_changed = True

        if state_changed:
            self.set_state(t, state)
