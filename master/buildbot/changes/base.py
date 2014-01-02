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

from twisted.application import service
from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.python import log
from zope.interface import implements

from buildbot import util
from buildbot.interfaces import IChangeSource


class ChangeSource(service.Service, util.ComparableMixin):
    implements(IChangeSource)

    master = None
    "if C{self.running} is true, then C{cs.master} points to the buildmaster."

    def describe(self):
        pass


class PollingChangeSource(ChangeSource):

    """
    Utility subclass for ChangeSources that use some kind of periodic polling
    operation.  Subclasses should define C{poll} and set C{self.pollInterval}.
    The rest is taken care of.

    Any subclass will be available via the "poller" webhook.
    """

    pollInterval = 60
    "time (in seconds) between calls to C{poll}"

    pollAtLaunch = False
    "determines when the first poll occurs. True = immediately on launch, False = wait for one pollInterval."

    _loop = None

    def __init__(self, name=None, pollInterval=60 * 10, pollAtLaunch=False):
        if name:
            self.setName(name)
        self.pollInterval = pollInterval
        self.pollAtLaunch = pollAtLaunch

        self.doPoll = util.misc.SerializedInvocation(self.doPoll)

    def doPoll(self):
        """
        This is the method that is called by LoopingCall to actually poll.
        It may also be called by change hooks to request a poll.
        It is serialiazed - if you call it while a poll is in progress
        then the 2nd invocation won't start until the 1st has finished.
        """
        d = defer.maybeDeferred(self.poll)
        d.addErrback(log.err, 'while polling for changes')
        return d

    def poll(self):
        """
        Perform the polling operation, and return a deferred that will fire
        when the operation is complete.  Failures will be logged, but the
        method will be called again after C{pollInterval} seconds.
        """

    def startLoop(self):
        self._loop = task.LoopingCall(self.doPoll)
        self._loop.start(self.pollInterval, now=self.pollAtLaunch)

    def stopLoop(self):
        if self._loop and self._loop.running:
            self._loop.stop()
            self._loop = None

    def startService(self):
        ChangeSource.startService(self)

        # delay starting doing anything until the reactor is running - if
        # services are still starting up, they may miss an initial flood of
        # changes
        if self.pollInterval:
            reactor.callWhenRunning(self.startLoop)
        else:
            reactor.callWhenRunning(self.doPoll)

    def stopService(self):
        self.stopLoop()
        return ChangeSource.stopService(self)
