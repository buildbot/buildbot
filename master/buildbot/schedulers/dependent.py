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
from buildbot import util
from buildbot.status.results import SUCCESS, WARNINGS
from buildbot.schedulers import base

class Dependent(base.BaseScheduler):

    compare_attrs = base.BaseScheduler.compare_attrs + ('upstream_name',)

    def __init__(self, name, upstream, builderNames, properties={}):
        base.BaseScheduler.__init__(self, name, builderNames, properties)
        assert base.isScheduler(upstream), \
                "upstream must be another Scheduler instance"
        self.upstream_name = upstream.name
        self._buildset_addition_subscr = None
        self._buildset_completion_subscr = None

        # the subscription lock makes sure that we're done inserting a
        # subcription into the DB before registering that the buildset is
        # complete.
        self._subscription_lock = defer.DeferredLock()

    def startService(self):
        self._buildset_addition_subscr = \
                self.master.subscribeToBuildsets(self._buildsetAdded)
        self._buildset_completion_subscr = \
                self.master.subscribeToBuildsetCompletions(self._buildsetCompleted)
        # check for any buildsets completed before we started
        d = self._checkCompletedBuildsets(None, None)
        d.addErrback(log.err, 'while checking for completed buildsets in start')

    def stopService(self):
        if self._buildset_addition_subscr:
            self._buildset_addition_subscr.unsubscribe()
        if self._buildset_completion_subscr:
            self._buildset_completion_subscr.unsubscribe()
        return defer.succeed(None)

    @util.deferredLocked('_subscription_lock')
    def _buildsetAdded(self, bsid=None, properties=None, **kwargs):
        # check if this was submitetted by our upstream by checking the
        # scheduler property
        submitter = properties.get('scheduler', (None, None))[0]
        if submitter != self.upstream_name:
            return

        # record our interest in this buildset, both locally and in the
        # database
        d = self.master.db.buildsets.subscribeToBuildset(
                                        self.schedulerid, bsid)
        d.addErrback(log.err, 'while subscribing to buildset %d' % bsid)

    def _buildsetCompleted(self, bsid, result):
        d = self._checkCompletedBuildsets(bsid, result)
        d.addErrback(log.err, 'while checking for completed buildsets')

    @util.deferredLocked('_subscription_lock')
    @defer.deferredGenerator
    def _checkCompletedBuildsets(self, bsid, result):
        wfd = defer.waitForDeferred(
            self.master.db.buildsets.getSubscribedBuildsets(self.schedulerid))
        yield wfd
        subs = wfd.getResult()

        for (sub_bsid, sub_ssid, sub_complete, sub_results) in subs:
            # skip incomplete builds, handling the case where the 'complete'
            # column has not been updated yet
            if not sub_complete and sub_bsid != bsid:
                continue

            # build a dependent build if the status is appropriate
            if sub_results in (SUCCESS, WARNINGS):
                wfd = defer.waitForDeferred(
                    self.addBuildsetForSourceStamp(ssid=sub_ssid,
                                               reason='downstream'))
                yield wfd
                wfd.getResult()

            # and regardless of status, remove the subscription
            wfd = defer.waitForDeferred(
                self.master.db.buildsets.unsubscribeFromBuildset(
                                          self.schedulerid, sub_bsid))
            yield wfd
            wfd.getResult()
