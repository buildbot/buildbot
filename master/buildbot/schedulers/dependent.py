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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer

from buildbot import config
from buildbot import interfaces
from buildbot import util
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.schedulers import base


class Dependent(base.BaseScheduler):

    compare_attrs = ('upstream_name',)

    def __init__(self, name, upstream, builderNames, **kwargs):
        base.BaseScheduler.__init__(self, name, builderNames, **kwargs)
        if not interfaces.IScheduler.providedBy(upstream):
            config.error(
                "upstream must be another Scheduler instance")
        self.upstream_name = upstream.name
        self._buildset_new_consumer = None
        self._buildset_complete_consumer = None
        self._cached_upstream_bsids = None

        # the subscription lock makes sure that we're done inserting a
        # subscription into the DB before registering that the buildset is
        # complete.
        self._subscription_lock = defer.DeferredLock()

    @defer.inlineCallbacks
    def activate(self):
        yield base.BaseScheduler.deactivate(self)

        if not self.enabled:
            return

        self._buildset_new_consumer = yield self.master.mq.startConsuming(
            self._buildset_new_cb,
            ('buildsets', None, 'new'))
        # TODO: refactor to subscribe only to interesting buildsets, and
        # subscribe to them directly, via the data API
        self._buildset_complete_consumer = yield self.master.mq.startConsuming(
            self._buildset_complete_cb,
            ('buildsets', None, 'complete'))

        # check for any buildsets completed before we started
        yield self._checkCompletedBuildsets(None, )

    @defer.inlineCallbacks
    def deactivate(self):
        # the base deactivate will unsubscribe from new changes
        yield base.BaseScheduler.deactivate(self)

        if not self.enabled:
            return

        if self._buildset_new_consumer:
            self._buildset_new_consumer.stopConsuming()
        if self._buildset_complete_consumer:
            self._buildset_complete_consumer.stopConsuming()
        self._cached_upstream_bsids = None

    @util.deferredLocked('_subscription_lock')
    def _buildset_new_cb(self, key, msg):
        # check if this was submitted by our upstream
        if msg['scheduler'] != self.upstream_name:
            return

        # record our interest in this buildset
        return self._addUpstreamBuildset(msg['bsid'])

    def _buildset_complete_cb(self, key, msg):
        return self._checkCompletedBuildsets(msg['bsid'])

    @util.deferredLocked('_subscription_lock')
    @defer.inlineCallbacks
    def _checkCompletedBuildsets(self, bsid):
        subs = yield self._getUpstreamBuildsets()

        sub_bsids = []
        for (sub_bsid, sub_ssids, sub_complete, sub_results) in subs:
            # skip incomplete builds, handling the case where the 'complete'
            # column has not been updated yet
            if not sub_complete and sub_bsid != bsid:
                continue

            # build a dependent build if the status is appropriate.  Note that
            # this uses the sourcestamps from the buildset, not from any of the
            # builds performed to complete the buildset (since those might
            # differ from one another)
            if sub_results in (SUCCESS, WARNINGS):
                yield self.addBuildsetForSourceStamps(
                    sourcestamps=[ssid for ssid in sub_ssids],
                    reason=u'downstream')

            sub_bsids.append(sub_bsid)

        # and regardless of status, remove the subscriptions
        yield self._removeUpstreamBuildsets(sub_bsids)

    @defer.inlineCallbacks
    def _updateCachedUpstreamBuilds(self):
        if self._cached_upstream_bsids is None:
            bsids = yield self.master.db.state.getState(self.objectid,
                                                        'upstream_bsids', [])
            self._cached_upstream_bsids = bsids

    @defer.inlineCallbacks
    def _getUpstreamBuildsets(self):
        # get a list of (bsid, ssids, complete, results) for all
        # upstream buildsets
        yield self._updateCachedUpstreamBuilds()

        changed = False
        rv = []
        for bsid in self._cached_upstream_bsids[:]:
            buildset = yield self.master.data.get(('buildsets', str(bsid)))
            if not buildset:
                self._cached_upstream_bsids.remove(bsid)
                changed = True
                continue

            ssids = [ss['ssid'] for ss in buildset['sourcestamps']]
            rv.append((bsid, ssids, buildset['complete'], buildset['results']))

        if changed:
            yield self.master.db.state.setState(self.objectid,
                                                'upstream_bsids', self._cached_upstream_bsids)

        defer.returnValue(rv)

    @defer.inlineCallbacks
    def _addUpstreamBuildset(self, bsid):
        yield self._updateCachedUpstreamBuilds()

        if bsid not in self._cached_upstream_bsids:
            self._cached_upstream_bsids.append(bsid)

            yield self.master.db.state.setState(self.objectid,
                                                'upstream_bsids', self._cached_upstream_bsids)

    @defer.inlineCallbacks
    def _removeUpstreamBuildsets(self, bsids):
        yield self._updateCachedUpstreamBuilds()

        old = set(self._cached_upstream_bsids)
        self._cached_upstream_bsids = list(old - set(bsids))

        yield self.master.db.state.setState(self.objectid,
                                            'upstream_bsids', self._cached_upstream_bsids)
