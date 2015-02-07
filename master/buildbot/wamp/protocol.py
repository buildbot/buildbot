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

    @wamp.register(u"org.buildbot.connect_slave")
    @defer.inlineCallbacks
    def connect_slave(self, name):
        slave = self.master.buildslaves.slaves[name]
        conn = Connection(self.master, slave)
        res = yield self.master.buildslaves.newConnection(conn, name)
        if res:
            yield slave.attached(conn)

    def getRemoteCommand(self, slavename, commandid):
        # TODO: sanity checks
        conn = self.master.buildslaves.slaves[slavename].conn
        rc = conn.curCommands[commandid]
        return rc
    # RemoteCommand base implementation

    @wamp.register(u"org.buildbot.remotecommand.update")
    def rc_update(self, slavename, commandid, updates):
        rc = self.getRemoteCommand(slavename, commandid)
        return rc.remoteCommand.remote_update(updates)

    @wamp.register(u"org.buildbot.remotecommand.complete")
    def rc_complete(self, slavename, commandid, failure=None):
        rc = self.getRemoteCommand(slavename, commandid)
        return rc.remoteCommand.remote_complete(failure)

    # FileWriter base implementation

    @wamp.register(u"org.buildbot.filewriter.write")
    def fw_write(self, slavename, commandid, data):
        rc = self.getRemoteCommand(slavename, commandid)
        return rc.filewriter.remote_write(data)

    @wamp.register(u"org.buildbot.filewriter.utime")
    def fw_utime(self, slavename, commandid, accessed_modified):
        rc = self.getRemoteCommand(slavename, commandid)
        return rc.filewriter.remote_utime(accessed_modified)

    @wamp.register(u"org.buildbot.filewriter.unpack")
    def fw_unpack(self, slavename, commandid):
        rc = self.getRemoteCommand(slavename, commandid)
        return rc.filewriter.remote_unpack()

    @wamp.register(u"org.buildbot.filewriter.close")
    def fw_close(self, slavename, commandid):
        rc = self.getRemoteCommand(slavename, commandid)
        return rc.filewriter.remote_close()

    # FileReader base implementation

    @wamp.register(u"org.buildbot.filereader.read")
    def fr_read(self, slavename, commandid, maxLength):
        rc = self.getRemoteCommand(slavename, commandid)
        return rc.filereader.remote_read(maxLength)

    @wamp.register(u"org.buildbot.filereader.close")
    def fr_close(self, slavename, commandid):
        rc = self.getRemoteCommand(slavename, commandid)
        return rc.filereader.remote_close()
