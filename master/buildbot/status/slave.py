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
from buildbot.util.eventual import eventually

class SlaveStatus:
    implements(interfaces.ISlaveStatus)

    admin = None
    host = None
    access_uri = None
    version = None
    connected = False
    graceful_shutdown = False
    paused = False

    def __init__(self, name):
        self.name = name
        self._lastMessageReceived = 0
        self.runningBuilds = []
        self.graceful_callbacks = []
        self.connect_times = []

    def getName(self):
        return self.name
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

    def recordConnectTime(self):
        # record this connnect, and keep data for the last hour
        now = time.time()
        self.connect_times = [ t for t in self.connect_times if t > now - 3600 ] + [ now ]

    def buildStarted(self, build):
        self.runningBuilds.append(build)
    def buildFinished(self, build):
        self.runningBuilds.remove(build)

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

    def asDict(self):
        result = {}
        # Constant
        result['name'] = self.getName()
        result['access_uri'] = self.getAccessURI()

        # Transient (since it changes when the slave reconnects)
        result['host'] = self.getHost()
        result['admin'] = self.getAdmin()
        result['version'] = self.getVersion()
        result['connected'] = self.isConnected()
        result['runningBuilds'] = [b.asDict() for b in self.getRunningBuilds()]
        return result

