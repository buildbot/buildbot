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
from twisted.application import service
from twisted.python import log
from buildbot.util import bbcollections, deferredLocked

class SchedulerManager(service.MultiService):
    def __init__(self, master):
        service.MultiService.__init__(self)
        self.master = master
        self.upstream_subscribers = bbcollections.defaultdict(list)
        self._updateLock = defer.DeferredLock()

    @deferredLocked('_updateLock')
    def updateSchedulers(self, newschedulers):
        """Add and start any Scheduler that isn't already a child of ours.
        Stop and remove any that are no longer in the list. Make sure each
        one has a schedulerid in the database."""
        # compute differences
        old = dict((s.name,s) for s in self)
        old_names = set(old)
        new = dict((s.name,s) for s in newschedulers)
        new_names = set(new)

        added_names = new_names - old_names
        removed_names = old_names - new_names

        # find any existing schedulers that need to be updated
        updated_names = set(name for name in (new_names & old_names)
                            if old[name] != new[name])

        log.msg("removing %d old schedulers, updating %d, and adding %d"
                % (len(removed_names), len(updated_names), len(added_names)))

        # treat updates as an add and a remove, for simplicity
        added_names |= updated_names
        removed_names |= updated_names

        # build a deferred chain that stops all of the removed schedulers,
        # *then* starts all of the added schedulers.  note that _setUpScheduler
        # is called before the service starts, and _shutDownSchedler is called
        # after the service is stopped.  Also note that this shuts down all
        # relevant schedulers before starting any schedulers - there's unlikely
        # to be any payoff to more parallelism
        d = defer.succeed(None)

        def stopScheduler(sch):
            d = defer.maybeDeferred(lambda : sch.disownServiceParent())
            d.addCallback(lambda _ : sch._shutDownScheduler())
            return d
        d.addCallback(lambda _ :
            defer.gatherResults([stopScheduler(old[n]) for n in removed_names]))

        # account for some renamed classes in buildbot - classes that have
        # changed their module import path, but should still access the same
        # state

        new_class_names = {
            # new : old
            'buildbot.schedulers.dependent.Dependent' :
                            'buildbot.schedulers.basic.Dependent',
            'buildbot.schedulers.basic.SingleBranchScheduler' :
                            'buildbot.schedulers.basic.Scheduler',
        }
        def startScheduler(sch):
            class_name = '%s.%s' % (sch.__class__.__module__,
                                    sch.__class__.__name__)
            class_name = new_class_names.get(class_name, class_name)
            d = self.master.db.schedulers.getSchedulerId(sch.name, class_name)
            d.addCallback(lambda schedulerid :
                    sch._setUpScheduler(schedulerid, self.master, self))
            d.addCallback(lambda _ :
                    sch.setServiceParent(self))
            return d
        d.addCallback(lambda _ :
            defer.gatherResults([startScheduler(new[n]) for n in added_names]))

        d.addErrback(log.err)
        return d
