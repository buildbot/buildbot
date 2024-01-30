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


class Watchdog:
    def __init__(self, reactor, fn, timeout):
        self._reactor = reactor
        self._fn = fn
        self._timeout = timeout
        self._delayed_call = None

    def _timed_out(self):
        self._delayed_call = None
        self._fn()

    def start(self):
        if self._delayed_call is None:
            self._delayed_call = self._reactor.callLater(self._timeout, self._timed_out)

    def stop(self):
        if self._delayed_call is not None:
            self._delayed_call.cancel()

    def notify(self):
        if self._delayed_call is None:
            return

        self._delayed_call.reset(self._timeout)
