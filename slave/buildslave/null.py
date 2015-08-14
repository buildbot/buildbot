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

from buildslave.base import BuildSlaveBase
from twisted.internet import defer


class LocalBuildSlave(BuildSlaveBase):

    @defer.inlineCallbacks
    def startService(self):
        # importing here to avoid dependency on buildbot master package
        from buildbot.buildslave.protocols.null import Connection

        yield BuildSlaveBase.startService(self)
        self.slavename = self.name
        conn = Connection(self.parent, self)
        # I don't have a master property, but my parent has.
        master = self.parent.master
        res = yield master.buildslaves.newConnection(conn, self.name)
        if res:
            yield self.parent.attached(conn)
