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

from buildbot.util import service
from twisted.internet import defer


class FakeBuildworkerManager(service.AsyncMultiService):

    def __init__(self):
        service.AsyncMultiService.__init__(self)
        self.setName('buildworkers')

        # BuildworkerRegistration instances keyed by buildworker name
        self.registrations = {}

        # connection objects keyed by buildworker name
        self.connections = {}

        # self.workers contains a ready BuildWorker instance for each
        # potential buildworker, i.e. all the ones listed in the config file.
        # If the worker is connected, self.workers[workername].worker will
        # contain a RemoteReference to their Bot instance. If it is not
        # connected, that attribute will hold None.
        self.workers = {}  # maps workername to BuildWorker

    def register(self, buildworker):
        buildworkerName = buildworker.workername
        reg = FakeBuildworkerRegistration(buildworker)
        self.registrations[buildworkerName] = reg
        return defer.succeed(reg)

    def _unregister(self, registration):
        del self.registrations[registration.buildworker.workername]

    def getBuildworkerByName(self, buildworkerName):
        return self.registrations[buildworkerName].buildworker

    def newConnection(self, conn, buildworkerName):
        assert buildworkerName not in self.connections
        self.connections[buildworkerName] = conn
        conn.info = {}

        def remove():
            del self.connections[buildworkerName]
        return defer.succeed(True)


class FakeBuildworkerRegistration(object):

    def __init__(self, buildworker):
        self.updates = []
        self.unregistered = False
        self.buildworker = buildworker

    def unregister(self):
        assert not self.unregistered, "called twice"
        self.unregistered = True
        return defer.succeed(None)

    def update(self, worker_config, global_config):
        if worker_config.workername not in self.updates:
            self.updates.append(worker_config.workername)
        return defer.succeed(None)
