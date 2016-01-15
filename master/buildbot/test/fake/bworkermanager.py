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


class FakeWorkerManager(service.AsyncMultiService):

    def __init__(self):
        service.AsyncMultiService.__init__(self)
        self.setName('buildslaves')

        # WorkerRegistration instances keyed by buildslave name
        self.registrations = {}

        # connection objects keyed by buildslave name
        self.connections = {}

        # self.slaves contains a ready Worker instance for each
        # potential buildslave, i.e. all the ones listed in the config file.
        # If the worker is connected, self.slaves[workername].slave will
        # contain a RemoteReference to their Bot instance. If it is not
        # connected, that attribute will hold None.
        self.slaves = {}  # maps workername to Worker

    def register(self, buildslave):
        buildslaveName = buildslave.workername
        reg = FakeWorkerRegistration(buildslave)
        self.registrations[buildslaveName] = reg
        return defer.succeed(reg)

    def _unregister(self, registration):
        del self.registrations[registration.buildslave.workername]

    def getBuildslaveByName(self, buildslaveName):
        return self.registrations[buildslaveName].buildslave

    def newConnection(self, conn, buildslaveName):
        assert buildslaveName not in self.connections
        self.connections[buildslaveName] = conn
        conn.info = {}

        def remove():
            del self.connections[buildslaveName]
        return defer.succeed(True)


class FakeWorkerRegistration(object):

    def __init__(self, buildslave):
        self.updates = []
        self.unregistered = False
        self.buildslave = buildslave

    def unregister(self):
        assert not self.unregistered, "called twice"
        self.unregistered = True
        return defer.succeed(None)

    def update(self, slave_config, global_config):
        if slave_config.workername not in self.updates:
            self.updates.append(slave_config.workername)
        return defer.succeed(None)
