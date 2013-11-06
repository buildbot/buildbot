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

from buildbot.interfaces import ITriggerableScheduler
from buildbot.process.properties import Properties
from buildbot.schedulers import base
from twisted.internet import defer
from twisted.python import failure


class Triggerable(base.BaseScheduler):
    implements(ITriggerableScheduler)

    compare_attrs = base.BaseScheduler.compare_attrs

    def __init__(self, name, builderNames, properties={}, **kwargs):
        base.BaseScheduler.__init__(self, name, builderNames, properties,
                                    **kwargs)
        self._waiters = {}
        self._bsc_subscription = None
        self.reason = "The Triggerable scheduler named '%s' triggered this build" % name

    def trigger(self, sourcestamps=None, set_props=None):
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
        d = self.addBuildsetForSourceStampSetDetails(self.reason,
                                                     sourcestamps, props)

        def setup_waiter(xxx_todo_changeme):
            (bsid, brids) = xxx_todo_changeme
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
