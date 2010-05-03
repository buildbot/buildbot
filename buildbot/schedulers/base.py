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
    Mixin to classify changes using self.filter, a filter.ChangeFilter instance.
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
        cm = self.parent.change_svc
        state = self.get_state(t)
        state_changed = False
        last_processed = state.get("last_processed", None)

        if last_processed is None:
            last_processed = state['last_processed'] = cm.getLatestChangeNumberNow(t)
            state_changed = True

        changes = cm.getChangesGreaterThan(last_processed, t)
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
