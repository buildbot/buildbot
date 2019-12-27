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

from buildbot.util import Notifier


class DeferWaiter:
    """ This class manages a set of Deferred objects and allows waiting for their completion
    """
    def __init__(self):
        self._waited = set()
        self._finish_notifier = Notifier()

    def _finished(self, _, d):
        self._waited.remove(id(d))
        if not self._waited:
            self._finish_notifier.notify(None)

    def add(self, d):
        if not isinstance(d, defer.Deferred):
            return

        self._waited.add(id(d))
        d.addBoth(self._finished, d)

    @defer.inlineCallbacks
    def wait(self):
        if not self._waited:
            return
        yield self._finish_notifier.wait()
