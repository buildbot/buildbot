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

from twisted.python import failure
from twisted.internet import defer
from buildbot.schedulers import base
from buildbot.process.properties import Properties
from buildbot import config

class Triggerable(base.BaseScheduler):

    compare_attrs = base.BaseScheduler.compare_attrs

    def __init__(self, name, builderNames, properties={}, **kwargs):
        base.BaseScheduler.__init__(self, name, builderNames, properties,
                                    **kwargs)
        self._waiters = {}
        self._bsc_subscription = None
        self.reason = "Triggerable(%s)" % name

    def trigger(self, sourcestamps = None, set_props=None):
        """Trigger this scheduler with the optional given list of sourcestamps
        Returns a deferred that will fire when the buildset is finished."""
        # properties for this buildset are composed of our own properties,
        # potentially overridden by anything from the triggering build
        props = Properties()
        props.updateFromProperties(self.properties)
        if set_props:
            props.updateFromProperties(set_props)

        # note that this does not use the buildset subscriptions mechanism, as
        # the duration of interest to the caller is bounded by the lifetime of
        # this process.
        d = self._addBuildsetForTrigger(self.reason, sourcestamps, props)
        def setup_waiter((bsid,brids)):
            d = defer.Deferred()
            self._waiters[bsid] = (d, brids)
            self._updateWaiters()
            return d
        d.addCallback(setup_waiter)
        return d

    def stopService(self):
        # cancel any outstanding subscription
        if self._bsc_subscription:
            self._bsc_subscription.unsubscribe()
            self._bsc_subscription = None

        # and errback any outstanding deferreds
        if self._waiters:
            msg = 'Triggerable scheduler stopped before build was complete'
            for d, brids in self._waiters.values():
                d.errback(failure.Failure(RuntimeError(msg)))
            self._waiters = {}

        return base.BaseScheduler.stopService(self)

    @defer.inlineCallbacks
    def _addBuildsetForTrigger(self, reason, sourcestamps,  properties):
        if sourcestamps is None:
            sourcestamps = {}

        # Define new setid for this set of triggering sourcestamps
        new_setid = yield self.master.db.sourcestampsets.addSourceStampSet()

        # Merge codebases with the passed list of sourcestamps
        # This results in a new sourcestamp for each codebase
        for codebase in self.codebases:
            ss = self.codebases[codebase].copy()
             # apply info from passed sourcestamps onto the configured default
             # sourcestamp attributes for this codebase.
            ss.update(sourcestamps.get(codebase,{}))

            # at least repository must be set, this is normaly forced except when 
            # codebases is not explicitly set in configuration file.
            ss_repository = ss.get('repository')
            if not ss_repository:
                config.error("The codebases argument is not set but still receiving " +
                             "non empty codebase values")

            # add sourcestamp to the new setid
            yield self.master.db.sourcestamps.addSourceStamp(
                        codebase=codebase,
                        repository=ss_repository,
                        branch=ss.get('branch', None),
                        revision=ss.get('revision', None),
                        project=ss.get('project', ''),
                        changeids=[c['number'] for c in getattr(ss, 'changes', [])],
                        patch_body=ss.get('patch_body', None),
                        patch_level=ss.get('patch_level', None),
                        patch_author=ss.get('patch_author', None),
                        patch_comment=ss.get('patch_comment', None),
                        sourcestampsetid=new_setid)

        bsid,brids = yield self.addBuildsetForSourceStamp(
                                setid=new_setid, reason=reason,
                                properties=properties)

        defer.returnValue((bsid,brids))


    def _updateWaiters(self):
        if self._waiters and not self._bsc_subscription:
            self._bsc_subscription = \
                    self.master.subscribeToBuildsetCompletions(
                                                self._buildsetComplete)
        elif not self._waiters and self._bsc_subscription:
            self._bsc_subscription.unsubscribe()
            self._bsc_subscription = None

    def _buildsetComplete(self, bsid, result):
        if bsid not in self._waiters:
            return

        # pop this bsid from the waiters list, and potentially unsubscribe
        # from completion notifications
        d, brids = self._waiters.pop(bsid)
        self._updateWaiters()

        # fire the callback to indicate that the triggered build is complete
        d.callback((result, brids))
