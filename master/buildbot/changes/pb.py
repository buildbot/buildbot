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


from twisted.python import log
from twisted.internet import defer

from buildbot.pbutil import NewCredPerspective
from buildbot.changes import base

class ChangePerspective(NewCredPerspective):

    def __init__(self, master, prefix):
        self.master = master
        self.prefix = prefix

    def attached(self, mind):
        return self
    def detached(self, mind):
        pass

    def perspective_addChange(self, changedict):
        log.msg("perspective_addChange called")
        files = []
        for path in changedict['files']:
            if self.prefix:
                if not path.startswith(self.prefix):
                    # this file does not start with the prefix, so ignore it
                    continue
                path = path[len(self.prefix):]
            files.append(path)
        changedict['files'] = files

        if files:
            return self.master.addChange(**changedict)
        else:
            return defer.succeed(None)

class PBChangeSource(base.ChangeSource):
    compare_attrs = ["user", "passwd", "port", "prefix", "port"]

    def __init__(self, user="change", passwd="changepw", port=None,
            prefix=None):

        self.user = user
        self.passwd = passwd
        self.port = port
        self.prefix = prefix
        self.registration = None

    def describe(self):
        # TODO: when the dispatcher is fixed, report the specific port
        if self.port is not None:
            portname = self.port
        else:
            portname = "all-purpose slaveport"
        d = "PBChangeSource listener on " + portname
        if self.prefix is not None:
            d += " (prefix '%s')" % self.prefix
        return d

    def startService(self):
        base.ChangeSource.startService(self)
        port = self.port
        if port is None:
            port = self.master.slavePortnum
        self.registration = self.master.pbmanager.register(
                port, self.user, self.passwd,
                self.getPerspective)

    def stopService(self):
        d = defer.maybeDeferred(base.ChangeSource.stopService, self)
        def unreg(_):
            if self.registration:
                return self.registration.unregister()
        d.addCallback(unreg)
        return d

    def getPerspective(self, mind, username):
        assert username == self.user
        return ChangePerspective(self.parent, self.prefix)
