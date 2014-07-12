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

from twisted.internet import task

# from
# http://twistedmatrix.com/trac/browser/trunk/twisted/internet/task.py?annotate=blame&rev=32000#L178


def reset(self):
    """
    Skip the next iteration and reset the timer.

    @since: 11.1
    """
    assert self.running, ("Tried to reset a LoopingCall that was "
                          "not running.")
    if self.call is not None:
        self.call.cancel()
        self.call = None
        self._expectNextCallAt = self.clock.seconds()
        self._reschedule()


def patch():
    task.LoopingCall.reset = reset
