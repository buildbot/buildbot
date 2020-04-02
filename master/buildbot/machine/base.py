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
# Portions Copyright Buildbot Team Members

from twisted.internet import defer
from zope.interface import implementer

from buildbot import interfaces
from buildbot.util import service


@implementer(interfaces.IMachine)
class Machine(service.BuildbotService):

    def checkConfig(self, name, **kwargs):
        super().checkConfig(**kwargs)
        self.name = name
        self.workers = []

    @defer.inlineCallbacks
    def reconfigService(self, name, **kwargs):
        yield super().reconfigService(**kwargs)
        assert self.name == name

    def registerWorker(self, worker):
        assert worker.machine_name == self.name
        self.workers.append(worker)

    def unregisterWorker(self, worker):
        assert worker in self.workers
        self.workers.remove(worker)

    def __repr__(self):
        return "<Machine '{}' at {}>".format(self.name, id(self))
