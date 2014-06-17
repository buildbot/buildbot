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

# The original author is Terry Jones, relicensed under GPLv2:
#   https://github.com/terrycojones/txrdq/tree/b6e45003

from twisted.internet import defer


class DeferredPool(object):

    """
    Maintain a pool of not-yet-fired deferreds and provide a mechanism to
    request a deferred that fires when the pool size goes to zero.
    """

    def __init__(self):
        self._pool = set()
        self._waiting = []

    def _fired(self, result, d):
        """
        Callback/errback each pooled deferred runs when it fires. The
        deferred first removes itself from the pool. If the pool is then
        empty, fire all the waiting deferreds (which were returned by
        notifyWhenEmpty).
        """
        self._pool.remove(d)
        if not self._pool:
            waiting, self._waiting = self._waiting, []
            for waiter in waiting:
                waiter.callback(None)
        return result

    def add(self, d):
        """
        Add a deferred to the pool.
        """
        d.addBoth(self._fired, d)
        self._pool.add(d)
        return d

    def notifyWhenEmpty(self, testImmediately=True):
        """
        Return a deferred that fires (with None) when the pool empties.  If
        testImmediately is True and the pool is empty, return an already
        fired deferred (via succeed).
        """
        if testImmediately and not self._pool:
            return defer.succeed(None)
        else:
            d = defer.Deferred()
            self._waiting.append(d)
            return d

    def status(self):
        """
        Return a tuple containing the number of deferreds that are
        outstanding and the number of deferreds that are waiting for the
        pool to empty.
        """
        return len(self._pool), len(self._waiting)
