# This file is part of .  Buildbot is free software: you can
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
# Copyright  Team Members

from autobahn import wamp
from buildbot.buildslave.protocols.wamp import Connection
from buildbot.util import service
from twisted.internet import defer


class SlaveProtoWampHandler(service.AsyncMultiService):

    def __init__(self, master):
        service.AsyncMultiService.__init__(self)
        self.master = master

    @wamp.subscribe(u"org.buildslave.joined")
    @defer.inlineCallbacks
    def connect_slave(self, slavename):
        slave = self.master.buildslaves.slaves[slavename]
        conn = Connection(self.master, slave)
        res = yield self.master.buildslaves.newConnection(conn, slavename)
        # several masters can fight for this slave. We only attach if we won
        if res:
            yield conn.attached()
            yield slave.attached(conn)
