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
from buildbot import util, interfaces, config
from buildbot.status.results import SUCCESS, WARNINGS
from buildbot.schedulers import base

class Dependent(base.BaseScheduler):

    compare_attrs = base.BaseScheduler.compare_attrs + ('upstream_name',)

    def __init__(self, name, upstream, builderNames, properties={}):
        base.BaseScheduler.__init__(self, name, builderNames, properties)
        if not interfaces.IScheduler.providedBy(upstream):
            config.error(
                "upstream must be another Scheduler instance")
        self.upstream_name = upstream.name
        self._buildset_addition_subscr = None
        self._buildset_completion_subscr = None
        self._cached_upstream_bsids = None

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
        self._cached_upstream_bsids = None
        return defer.succeed(None)

    @util.deferredLocked('_subscription_lock')
    def _buildsetAdded(self, bsid=None, properties=None, **kwargs):
        # check if this was submitetted by our upstream by checking the
        # scheduler property
        submitter = properties.get('scheduler', (None, None))[0]
        if submitter != self.upstream_name:
            return

        # record our interest in this buildset
        d = self._addUpstreamBuildset(bsid)
        d.addErrback(log.err, 'while subscribing to buildset %d' % bsid)

    def _buildsetCompleted(self, bsid, result):
        d = self._checkCompletedBuildsets(bsid, result)
        d.addErrback(log.err, 'while checking for completed buildsets')

    @util.deferredLocked('_subscription_lock')
    @defer.deferredGenerator
    def _checkCompletedBuildsets(self, bsid, result):
        wfd = defer.waitForDeferred(
            self._getUpstreamBuildsets())
        yield wfd
        subs = wfd.getResult()

        sub_bsids = []
        for (sub_bsid, sub_sssetid, sub_complete, sub_results) in subs:
            # skip incomplete builds, handling the case where the 'complete'
            # column has not been updated yet
            if not sub_complete and sub_bsid != bsid:
                continue

            # build a dependent build if the status is appropriate
            if sub_results in (SUCCESS, WARNINGS):
                wfd = defer.waitForDeferred(
                    self.addBuildsetForSourceStamp(setid=sub_sssetid,
                                               reason='downstream'))
                yield wfd
                wfd.getResult()

            sub_bsids.append(sub_bsid)

        # and regardless of status, remove the subscriptions
        wfd = defer.waitForDeferred(
            self._removeUpstreamBuildsets(sub_bsids))
        yield wfd
        wfd.getResult()

    @defer.deferredGenerator
    def _updateCachedUpstreamBuilds(self):
        if self._cached_upstream_bsids is None:
            wfd = defer.waitForDeferred(
                self.master.db.state.getState(self.objectid,
                                        'upstream_bsids', []))
            yield wfd
            self._cached_upstream_bsids = wfd.getResult()[:]

    @defer.deferredGenerator
    def _getUpstreamBuildsets(self):
        # get a list of (bsid, sssid, complete, results) for all
        # upstream buildsets
        wfd = defer.waitForDeferred(
            self._updateCachedUpstreamBuilds())
        yield wfd
        wfd.getResult()

        changed = False
        rv = []
        for bsid in self._cached_upstream_bsids[:]:
            wfd = defer.waitForDeferred(
                self.master.db.buildsets.getBuildset(bsid))
            yield wfd
            bsdict = wfd.getResult()
            if not bsdict:
                self._cached_upstream_bsids.remove(bsid)
                changed = True
                continue

            rv.append((bsid, bsdict['sourcestampsetid'], bsdict['complete'],
                bsdict['results']))

        if changed:
            wfd = defer.waitForDeferred(
                self.master.db.state.setState(self.objectid,
                                'upstream_bsids', self._cached_upstream_bsids))
            yield wfd
            wfd.getResult()

        yield rv

    @defer.deferredGenerator
    def _addUpstreamBuildset(self, bsid):
        wfd = defer.waitForDeferred(
            self._updateCachedUpstreamBuilds())
        yield wfd
        wfd.getResult()

        if bsid not in self._cached_upstream_bsids:
            self._cached_upstream_bsids.append(bsid)

            wfd = defer.waitForDeferred(
                self.master.db.state.setState(self.objectid,
                                'upstream_bsids', self._cached_upstream_bsids))
            yield wfd
            wfd.getResult()

    @defer.deferredGenerator
    def _removeUpstreamBuildsets(self, bsids):
        wfd = defer.waitForDeferred(
            self._updateCachedUpstreamBuilds())
        yield wfd
        wfd.getResult()

        old = set(self._cached_upstream_bsids)
        self._cached_upstream_bsids = list(old - set(bsids))

        wfd = defer.waitForDeferred(
            self.master.db.state.setState(self.objectid,
                            'upstream_bsids', self._cached_upstream_bsids))
        yield wfd
        wfd.getResult()

