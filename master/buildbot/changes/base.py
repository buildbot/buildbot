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
from twisted.python import log
from zope.interface import implements

from buildbot.interfaces import IChangeSource
from buildbot.util import service
from buildbot.util.poll import method as poll_method


class ChangeSource(service.ClusteredBuildbotService):
    implements(IChangeSource)

    def describe(self):
        pass

    # activity handling

    def activate(self):
        return defer.succeed(None)

    def deactivate(self):
        return defer.succeed(None)

    # service handling

    def _getServiceId(self):
        return self.master.data.updates.findChangeSourceId(self.name)

    def _claimService(self):
        return self.master.data.updates.trySetChangeSourceMaster(self.serviceid,
                                                                 self.master.masterid)

    def _unclaimService(self):
        return self.master.data.updates.trySetChangeSourceMaster(self.serviceid,
                                                                 None)


class PollingChangeSource(ChangeSource):

    def __init__(self, name=None, pollInterval=60 * 10, pollAtLaunch=False):
        ChangeSource.__init__(self, name=name)
        self.pollInterval = pollInterval
        self.pollAtLaunch = pollAtLaunch

    def poll(self):
        pass

    @poll_method
    def doPoll(self):
        d = defer.maybeDeferred(self.poll)
        d.addErrback(log.err, 'while polling for changes')
        return d

    def force(self):
        self.doPoll()

    def activate(self):
        self.doPoll.start(interval=self.pollInterval, now=self.pollAtLaunch)

    def deactivate(self):
        return self.doPoll.stop()
