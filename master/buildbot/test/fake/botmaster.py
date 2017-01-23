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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer

from buildbot.util import service


class FakeBotMaster(service.AsyncMultiService):

    def __init__(self):
        service.AsyncMultiService.__init__(self)
        self.setName("fake-botmaster")
        self.locks = {}
        self.builders = {}
        self.buildsStartedForWorkers = []
        self.delayShutdown = False

    def getLockByID(self, lockid):
        if lockid not in self.locks:
            self.locks[lockid] = lockid.lockClass(lockid)
        # if the master.cfg file has changed maxCount= on the lock, the next
        # time a build is started, they'll get a new RealLock instance. Note
        # that this requires that MasterLock and WorkerLock (marker) instances
        # be hashable and that they should compare properly.
        return self.locks[lockid]

    def getLockFromLockAccess(self, access):
        return self.getLockByID(access.lockid)

    def getBuildersForWorker(self, workername):
        return self.builders.get(workername, [])

    def maybeStartBuildsForWorker(self, workername):
        self.buildsStartedForWorkers.append(workername)

    def workerLost(self, bot):
        pass

    def cleanShutdown(self, quickMode=False, stopReactor=True):
        self.shuttingDown = True
        if self.delayShutdown:
            self.shutdownDeferred = defer.Deferred()
            return self.shutdownDeferred
