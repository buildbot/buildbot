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

import copy

from buildbot import interfaces
from buildbot.util import ascii2unicode
from buildbot.util import json
from buildbot.util.eventual import eventually
from zope.interface import implements


class SlaveStatus:
    implements(interfaces.ISlaveStatus)

    connected = False
    graceful_shutdown = False
    paused = False

    def __init__(self, name):
        self.name = name
        self._lastMessageReceived = 0
        self.runningBuilds = []
        self.graceful_callbacks = []
        self.pause_callbacks = []
        self.info = {}
        self.info_change_callbacks = []
        self.connect_times = []

    def getName(self):
        return self.name

    def getAdmin(self):
        return self.getInfo('admin')

    def getHost(self):
        return self.getInfo('host')

    def getAccessURI(self):
        return self.getInfo('access_uri')

    def getVersion(self):
        return self.getInfo('version')

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
        return len([t for t in self.connect_times if t > then])

    def setAdmin(self, admin):
        self.updateInfo(admin=admin)

    def setHost(self, host):
        self.updateInfo(host=host)

    def setAccessURI(self, access_uri):
        self.updateInfo(access_uri=access_uri)

    def setVersion(self, version):
        self.updateInfo(version=version)

    def setConnected(self, isConnected):
        self.connected = isConnected

    def setLastMessageReceived(self, when):
        self._lastMessageReceived = when

    def setPaused(self, isPaused):
        self.paused = isPaused
        for cb in self.pause_callbacks:
            eventually(cb, isPaused)

    def addPauseWatcher(self, watcher):
        """Add watcher to the list of watchers to be notified when the
        pause flag is changed."""
        if watcher not in self.pause_callbacks:
            self.pause_callbacks.append(watcher)

    def removePauseWatcher(self, watcher):
        """Remove watcher from the list of watchers to be notified when the
        pause shutdown flag is changed."""
        if watcher in self.pause_callbacks:
            self.pause_callbacks.remove(watcher)

    def recordConnectTime(self):
        # record this connnect, and keep data for the last hour
        now = time.time()
        self.connect_times = [t for t in self.connect_times if t > now - 3600] + [now]

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
        if watcher not in self.graceful_callbacks:
            self.graceful_callbacks.append(watcher)

    def removeGracefulWatcher(self, watcher):
        """Remove watcher from the list of watchers to be notified when the
        graceful shutdown flag is changed."""
        if watcher in self.graceful_callbacks:
            self.graceful_callbacks.remove(watcher)

    def getInfoAsDict(self):
        return copy.deepcopy(self.info)

    def setInfoDict(self, info):
        self.info = info

    def getInfo(self, key, default=None):
        return self.info.get(key, default)

    def updateInfo(self, **kwargs):
        # round-trip the value through json to 'normalize' it and
        # to ensure bad values dont get stuffed into the dictionary
        new_values = json.loads(json.dumps(kwargs))

        for special_key in ['admin', 'host']:
            if special_key in new_values:
                new_values[special_key] = ascii2unicode(new_values[special_key])

        # try to see if anything changed (so we should inform watchers)
        for k, v in new_values.iteritems():
            if k not in self.info:
                break
            if self.info[k] != v:
                break
        else:
            # nothing changed so just bail now
            return

        self.info.update(new_values)

        for watcher in self.info_change_callbacks:
            eventually(watcher, self.getInfoAsDict())

    def hasInfo(self, key):
        return key in self.info

    def addInfoWatcher(self, watcher):
        if watcher not in self.info_change_callbacks:
            self.info_change_callbacks.append(watcher)

    def removeInfoWatcher(self, watcher):
        if watcher in self.info_change_callbacks:
            self.info_change_callbacks.remove(watcher)

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
        result['info'] = self.getInfoAsDict()
        return result
