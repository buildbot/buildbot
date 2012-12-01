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

"""
Classes to handle subscriptions to event streams.

This will eventually (in the 0.9.x timeframe) be replaced with an
implementation based on message passing.  Users should be aware they will need
to rewrite any custom code that touches this module!
"""

from twisted.python import failure, log

class SubscriptionPoint(object):
    """
    Something that can be subscribed to.
    """
    def __init__(self, name):
        self.name = name
        self.subscriptions = set()

    def __str__(self):
        return "<SubscriptionPoint '%s'>" % self.name

    def subscribe(self, callback):
        """Add C{callback} to the subscriptions; returns a L{Subscription}
        instance."""
        sub = Subscription(self, callback)
        self.subscriptions.add(sub)
        return sub

    def deliver(self, *args, **kwargs):
        """
        Deliver the given args and keyword args to all of the current
        subscribers.
        """
        for sub in list(self.subscriptions):
            try:
                sub.callback(*args, **kwargs)
            except:
                log.err(failure.Failure(),
                        'while invoking callback %s to %s' % (sub.callback, self))

    def _unsubscribe(self, subscription):
        self.subscriptions.remove(subscription)

class Subscription(object):
    """
    Represents a subscription to a L{SubscriptionPoint}; use
    L{SubscriptionPoint.subscribe} to get an instance.
    """
    def __init__(self, subpt, callback):
        self.subpt = subpt
        self.callback = callback

    def unsubscribe(self):
        "Cancel the subscription"
        self.subpt._unsubscribe(self)
