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
from twisted.python import failure
from twisted.python import log

from buildbot.util import Notifier


class SubscriptionPoint:

    def __init__(self, name):
        self.name = name
        self.subscriptions = set()
        self._unfinished_deliveries = []
        self._unfinished_notifier = Notifier()

    def __str__(self):
        return "<SubscriptionPoint '%s'>" % self.name

    def subscribe(self, callback):
        sub = Subscription(self, callback)
        self.subscriptions.add(sub)
        return sub

    def deliver(self, *args, **kwargs):
        self._unfinished_deliveries.append(self)
        for sub in list(self.subscriptions):
            try:
                d = sub.callback(*args, **kwargs)
                if isinstance(d, defer.Deferred):
                    self._unfinished_deliveries.append(d)
                    d.addBoth(self._notify_delivery_finished, d)

            except Exception:
                log.err(failure.Failure(),
                        'while invoking callback %s to %s' % (sub.callback, self))

        self._notify_delivery_finished(None, self)

    def waitForDeliveriesToFinish(self):
        # returns a deferred
        if not self._unfinished_deliveries:
            return defer.succeed(None)
        return self._unfinished_notifier.wait()

    def _unsubscribe(self, subscription):
        self.subscriptions.remove(subscription)

    def _notify_delivery_finished(self, _, d):
        self._unfinished_deliveries.remove(d)
        if not self._unfinished_deliveries:
            self._unfinished_notifier.notify(None)


class Subscription:

    def __init__(self, subpt, callback):
        self.subpt = subpt
        self.callback = callback

    def unsubscribe(self):
        self.subpt._unsubscribe(self)
