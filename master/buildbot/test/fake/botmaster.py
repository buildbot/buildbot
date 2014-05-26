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


class FakeBotMaster(service.MultiService):

    def __init__(self, master):
        service.MultiService.__init__(self)
        self.setName("fake-botmaster")
        self.master = master
        self.locks = {}
        self.builders = {}
        self.buildsStartedForSlaves = []

    def getLockByID(self, lockid):
        if lockid not in self.locks:
            self.locks[lockid] = lockid.lockClass(lockid)
        # if the master.cfg file has changed maxCount= on the lock, the next
        # time a build is started, they'll get a new RealLock instance. Note
        # that this requires that MasterLock and SlaveLock (marker) instances
        # be hashable and that they should compare properly.
        return self.locks[lockid]

    def getLockFromLockAccess(self, access):
        return self.getLockByID(access.lockid)

    def getBuildersForSlave(self, slavename):
        return self.builders.get(slavename, [])

    def maybeStartBuildsForSlave(self, slavename):
        self.buildsStartedForSlaves.append(slavename)
