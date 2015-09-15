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

from buildworker.base import BuildWorkerBase
from twisted.internet import defer


class LocalBuildWorker(BuildWorkerBase):

    @defer.inlineCallbacks
    def startService(self):
        # importing here to avoid dependency on buildbot master package
        from buildbot.buildworker.protocols.null import Connection

        yield BuildWorkerBase.startService(self)
        self.workername = self.name
        conn = Connection(self.parent, self)
        # I don't have a master property, but my parent has.
        master = self.parent.master
        res = yield master.buildworkers.newConnection(conn, self.name)
        if res:
            yield self.parent.attached(conn)
