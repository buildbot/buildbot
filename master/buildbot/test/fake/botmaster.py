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

from buildbot.process import botmaster
from buildbot.util import service


class FakeBotMaster(service.AsyncMultiService, botmaster.LockRetrieverMixin):

    def __init__(self):
        super().__init__()
        self.setName("fake-botmaster")
        self.builders = {}  # dictionary mapping worker names to builders
        self.buildsStartedForWorkers = []
        self.delayShutdown = False

    def getBuildersForWorker(self, workername):
        return self.builders.get(workername, [])

    def maybeStartBuildsForWorker(self, workername):
        self.buildsStartedForWorkers.append(workername)

    def maybeStartBuildsForAllBuilders(self):
        self.buildsStartedForWorkers += self.builders.keys()

    def workerLost(self, bot):
        pass

    def cleanShutdown(self, quickMode=False, stopReactor=True):
        self.shuttingDown = True
        if self.delayShutdown:
            self.shutdownDeferred = defer.Deferred()
            return self.shutdownDeferred
        return None
