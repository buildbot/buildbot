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


class FakeBuildslaveManager(service.MultiService):

    def __init__(self, master):
        service.MultiService.__init__(self)
        self.setName('buildslaves')
        self.master = master

        # BuildslaveRegistration instances keyed by buildslave name
        self.registrations = {}

        # connection objects keyed by buildslave name
        self.connections = {}

    def register(self, buildslave):
        buildslaveName = buildslave.slavename
        reg = FakeBuildslaveRegistration(buildslave)
        self.registrations[buildslaveName] = reg
        return defer.succeed(reg)

    def _unregister(self, registration):
        del self.registrations[registration.buildslave.slavename]

    def getBuildslaveByName(self, buildslaveName):
        return self.registrations[buildslaveName].buildslave

    def newConnection(self, conn, buildslaveName):
        assert buildslaveName not in self.connections
        self.connections[buildslaveName] = conn
        def remove():
            del self.connections[buildslaveName]
        return defer.succeed(True)


class FakeBuildslaveRegistration(object):

    def __init__(self, buildslave):
        self.updates = []
        self.unregistered = False
        self.buildslave = buildslave

    def unregister(self):
        assert not self.unregistered, "called twice"
        self.unregistered = True
        return defer.succeed(None)

    def update(self, slave_config, global_config):
        self.updates.append(slave_config.slavename)
        return defer.succeed(None)

