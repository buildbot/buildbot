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

import os

from buildbot.process import properties
from twisted.internet import defer


class FakeSlave(object):
    slavename = 'test'

    def __init__(self, master):
        self.master = master
        self.properties = properties.Properties()

    def acquireLocks(self):
        pass

    def releaseLocks(self):
        pass

    def attached(self, bot):
        self.slave_system = 'posix'
        self.path_module = os.path
        self.buildslaveid = 1234
        self.slave_basedir = '/sl'
        return defer.succeed(None)

    def detached(self, mind):
        pass

    def addSlaveBuilder(self, sb):
        pass

    def removeSlaveBuilder(self, sb):
        pass

    def buildFinished(self, sb):
        pass

    def canStartBuild(self):
        pass
