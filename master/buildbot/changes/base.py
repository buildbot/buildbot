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
from twisted.application import service
from twisted.internet import defer, task
from twisted.python import log

from buildbot.interfaces import IChangeSource
from buildbot import util

class ChangeSource(service.Service, util.ComparableMixin):
    implements(IChangeSource)

    def describe(self):
        return "no description"

class PollingChangeSource(ChangeSource):
    """
    Utility subclass for ChangeSources that use some kind of periodic polling
    operation.  Subclasses should define C{poll} and set C{self.pollInterval}.
    The rest is taken care of.
    """

    pollInterval = 60
    "time (in seconds) between calls to C{poll}"

    _loop = None
    volatile = ['_loop'] # prevents Twisted from pickling this value

    def poll(self):
        """
        Perform the polling operation, and return a deferred that will fire
        when the operation is complete.  Failures will be logged, but the
        method will be called again after C{pollInterval} seconds.
        """

    def startService(self):
        ChangeSource.startService(self)
        def do_poll():
            d = defer.maybeDeferred(self.poll)
            d.addErrback(log.err)
            return d
        self._loop = task.LoopingCall(do_poll)
        self._loop.start(self.pollInterval)

    def stopService(self):
        self._loop.stop()
        return ChangeSource.stopService(self)

