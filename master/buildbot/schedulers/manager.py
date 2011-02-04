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
