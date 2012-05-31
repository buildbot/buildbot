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
from twisted.python import log, reflect
from buildbot.process import metrics
from buildbot import config, util

class SchedulerManager(config.ReconfigurableServiceMixin,
                       service.MultiService):
    def __init__(self, master):
        service.MultiService.__init__(self)
        self.setName('scheduler_manager')
        self.master = master

    @defer.inlineCallbacks
    def reconfigService(self, new_config):
        timer = metrics.Timer("SchedulerManager.reconfigService")
        timer.start()

        old_by_name = dict((sch.name, sch) for sch in self)
        old_set = set(old_by_name.iterkeys())
        new_by_name = new_config.schedulers
        new_set = set(new_by_name.iterkeys())

        removed_names, added_names = util.diffSets(old_set, new_set)

        # find any schedulers that don't know how to reconfig, and, if they
        # have changed, add them to both removed and added, so that we
        # run the new version.  While we're at it, find any schedulers whose
        # fully qualified class name has changed, and consider those a removal
        # and re-add as well.
        for n in old_set & new_set:
            old = old_by_name[n]
            new = new_by_name[n]
            # detect changed class name
            if reflect.qual(old.__class__) != reflect.qual(new.__class__):
                removed_names.add(n)
                added_names.add(n)

            # compare using ComparableMixin if they don't support reconfig
            elif not hasattr(old, 'reconfigService'):
                if old != new:
                    removed_names.add(n)
                    added_names.add(n)

        # removals first

        for sch_name in removed_names:
            log.msg("removing scheduler '%s'" % (sch_name,))
            sch = old_by_name[sch_name]
            yield defer.maybeDeferred(lambda :
                        sch.disownServiceParent())
            sch.master = None

        # .. then additions

        for sch_name in added_names:
            log.msg("adding scheduler '%s'" % (sch_name,))
            sch = new_by_name[sch_name]

            # get the scheduler's objectid
            class_name = '%s.%s' % (sch.__class__.__module__,
                                    sch.__class__.__name__)
            objectid = yield self.master.db.state.getObjectId(
                                    sch.name, class_name)

            # set up the scheduler
            sch.objectid = objectid
            sch.master = self.master

            # *then* attacah and start it
            sch.setServiceParent(self)

        metrics.MetricCountEvent.log("num_schedulers", len(list(self)),
                                    absolute=True)

        # reconfig any newly-added schedulers, as well as existing
        yield config.ReconfigurableServiceMixin.reconfigService(self,
                                                        new_config)

        timer.stop()
