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

from twisted.internet import defer
from twisted.python import log
from buildbot.util import loop
from buildbot.util import collections
from buildbot.util.eventual import eventually

class SchedulerManager(loop.MultiServiceLoop):
    def __init__(self, master, db, change_svc):
        loop.MultiServiceLoop.__init__(self)
        self.master = master
        self.db = db
        self.change_svc = change_svc
        self.upstream_subscribers = collections.defaultdict(list)

    def updateSchedulers(self, newschedulers):
        """Add and start any Scheduler that isn't already a child of ours.
        Stop and remove any that are no longer in the list. Make sure each
        one has a schedulerid in the database."""
        # TODO: this won't tolerate reentrance very well
        new_names = set()
        added = set()
        removed = set()
        for s in newschedulers:
            new_names.add(s.name)
            try:
                old = self.getServiceNamed(s.name)
            except KeyError:
                old = None
            if old:
                if old.compareToOther(s):
                    removed.add(old)
                    added.add(s)
                else:
                    pass # unchanged
            else:
                added.add(s)
        for old in list(self):
            if old.name not in new_names:
                removed.add(old)
        #if removed or added:
        #    # notify Downstream schedulers to potentially pick up
        #    # new schedulers now that we have removed and added some
        #    def updateDownstreams(res):
        #        log.msg("notifying downstream schedulers of changes")
        #        for s in newschedulers:
        #            if interfaces.IDownstreamScheduler.providedBy(s):
        #                s.checkUpstreamScheduler()
        #    d.addCallback(updateDownstreams)
        log.msg("removing %d old schedulers, adding %d new ones"
                % (len(removed), len(added)))
        dl = [defer.maybeDeferred(s.disownServiceParent) for s in removed]
        d = defer.gatherResults(dl)
        d.addCallback(lambda ign: self.db.addSchedulers(added))
        def _attach(ign):
            for s in added:
                s.setServiceParent(self)
            self.upstream_subscribers = collections.defaultdict(list)
            for s in list(self):
                if s.upstream_name:
                    self.upstream_subscribers[s.upstream_name].append(s)
            eventually(self.trigger)
        d.addCallback(_attach)
        d.addErrback(log.err)
        return d

    def publish_buildset(self, upstream_name, bsid, t):
        if upstream_name in self.upstream_subscribers:
            for s in self.upstream_subscribers[upstream_name]:
                s.buildSetSubmitted(bsid, t)

    def trigger_add_change(self, category, changenumber):
        self.trigger()
    def trigger_modify_buildset(self, category, *bsids):
        # TODO: this could just run the schedulers that have subscribed to
        # scheduler_upstream_buildsets, or even just the ones that subscribed
        # to hear about the specific buildsetid
        self.trigger()
