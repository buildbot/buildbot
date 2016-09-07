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

import time
from zope.interface import implements
from buildbot import interfaces
from buildbot.status.results import WARNINGS, EXCEPTION, FAILURE, SUCCESS, RESUME, CANCELED, NOT_REBUILT
from buildbot.util.eventual import eventually
from twisted.internet import defer

class SlaveStatus:
    implements(interfaces.ISlaveStatus)

    admin = None
    host = None
    access_uri = None
    version = None
    connected = False
    graceful_shutdown = False
    friendly_name = None
    paused = False

    def __init__(self, name):
        self.name = name
        self._lastMessageReceived = 0
        self.runningBuilds = []
        self.graceful_callbacks = []
        self.connect_times = []
        self.master = None
        self.health = 0
        self.fqdn = None
        self.eid = -1

    def getName(self):
        return self.name
    def getFriendlyName(self):
        return self.friendly_name
    def getAdmin(self):
        return self.admin
    def getHost(self):
        return self.host
    def getAccessURI(self):
        return self.access_uri
    def getVersion(self):
        return self.version
    def isConnected(self):
        return self.connected
    def isPaused(self):
        return self.paused
    def lastMessageReceived(self):
        return self._lastMessageReceived
    def getRunningBuilds(self):
        return self.runningBuilds
    def getConnectCount(self):
        then = time.time() - 3600
        return len([ t for t in self.connect_times if t > then ])

    def setFriendlyName(self, name):
        self.friendly_name = name
    def setAdmin(self, admin):
        self.admin = admin
    def setHost(self, host):
        self.host = host
    def setAccessURI(self, access_uri):
        self.access_uri = access_uri
    def setVersion(self, version):
        self.version = version
    def setConnected(self, isConnected):
        self.connected = isConnected
    def setLastMessageReceived(self, when):
        self._lastMessageReceived = when
    def setPaused(self, isPaused):
        self.paused = isPaused
        if not self.paused and self.name in self.master.botmaster.slaves:
            self.master.botmaster.maybeStartBuildsForSlave(self.name)


    def setMaster(self, master):
        self.master = master

    def recordConnectTime(self):
        # record this connnect, and keep data for the last hour
        now = time.time()
        self.connect_times = [ t for t in self.connect_times if t > now - 3600 ] + [ now ]

    def buildStarted(self, build):
        self.runningBuilds.append(build)

    def removeRunningBuild(self, build_status):
        if build_status in self.runningBuilds:
            self.runningBuilds.remove(build_status)

    @defer.inlineCallbacks
    def buildFinished(self, build):
        shouldUpdateHealth = build.results not in (RESUME, CANCELED, NOT_REBUILT) and \
                             (self.health != SUCCESS or build.results != SUCCESS)
        if shouldUpdateHealth:
            yield self.updateHealth()
        self.removeRunningBuild(build)

    def getGraceful(self):
        """Return the graceful shutdown flag"""
        return self.graceful_shutdown
    def setGraceful(self, graceful):
        """Set the graceful shutdown flag, and notify all the watchers"""
        self.graceful_shutdown = graceful
        for cb in self.graceful_callbacks:
            eventually(cb, graceful)
    def addGracefulWatcher(self, watcher):
        """Add watcher to the list of watchers to be notified when the
        graceful shutdown flag is changed."""
        if not watcher in self.graceful_callbacks:
            self.graceful_callbacks.append(watcher)
    def removeGracefulWatcher(self, watcher):
        """Remove watcher from the list of watchers to be notified when the
        graceful shutdown flag is changed."""
        if watcher in self.graceful_callbacks:
            self.graceful_callbacks.remove(watcher)

    def getBuilders(self):
        status = self.master.status
        my_builders = []
        for bname in status.getBuilderNames():
            b = status.getBuilder(bname)
            for bs in b.getAllSlaves():
                if bs.getName() == self.name:
                    my_builders.append(b)

        return my_builders

    @defer.inlineCallbacks
    def getRecentBuilds(self, num_builds=15):
        status = self.master.status
        builds = yield status.generateFinishedBuildsAsync(num_builds=num_builds, slavename=self.name)
        defer.returnValue(builds)

    @defer.inlineCallbacks
    def updateHealth(self):
        num_builds = 15
        health = 0
        builds = yield self.getRecentBuilds(num_builds)

        if len(builds) == 0:
            self.health = 0
            return

        build_weight = 1.0 / len(builds)

        for b in builds:
            if b.getResults() != FAILURE and b.getResults() != WARNINGS and b.getResults() != EXCEPTION:
                health += build_weight

        if health >= 0.8:
            self.health = 0
        elif health >= 0.5:
            self.health = -1
        else:
            self.health = -2

    def asDict(self, include_build_steps=True, include_build_props=True):
        result = {}
        # Constant
        result['name'] = self.getName()
        result['friendly_name'] = self.getFriendlyName()
        result['access_uri'] = self.getAccessURI()
        result["url"] = self.master.status.getURLForThing(self)

        # Transient (since it changes when the slave reconnects)
        result['host'] = self.getHost()
        result['admin'] = self.getAdmin()
        result['version'] = self.getVersion()
        result['connected'] = self.isConnected()
        builds = [b.asDict(include_steps=include_build_steps, include_properties=include_build_props)
                  for b in self.getRunningBuilds()]
        builds = sorted(builds, key=lambda b: b['isWaiting'])
        result['runningBuilds'] = builds
        result['lastMessage'] = self.lastMessageReceived()
        result['health'] = self.health
        result['fqdn'] = self.fqdn
        result['slaveManagerUrl'] = self.master.config.slaveManagerUrl
        result['eid'] = self.eid
        result['graceful_shutdown'] = self.graceful_shutdown
        result['paused'] = self.isPaused()
        return result

