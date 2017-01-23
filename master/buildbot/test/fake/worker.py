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

import os

from twisted.internet import defer

from buildbot.process import properties
from buildbot.test.fake import fakeprotocol


class FakeWorker(object):
    workername = 'test'

    def __init__(self, master):
        self.master = master
        self.conn = fakeprotocol.FakeConnection(master, self)
        self.properties = properties.Properties()
        self.workerid = 383

    def acquireLocks(self):
        pass

    def releaseLocks(self):
        pass

    def attached(self, conn):
        self.worker_system = 'posix'
        self.path_module = os.path
        self.workerid = 1234
        self.worker_basedir = '/wrk'
        return defer.succeed(None)

    def detached(self):
        pass

    def addWorkerForBuilder(self, wfb):
        pass

    def removeWorkerForBuilder(self, wfb):
        pass

    def buildFinished(self, wfb):
        pass

    def canStartBuild(self):
        pass

    def putInQuarantine(self):
        pass

    def resetQuarantine(self):
        pass
