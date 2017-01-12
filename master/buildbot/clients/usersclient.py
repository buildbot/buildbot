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

# this class is known to contain cruft and will be looked at later, so
# no current implementation utilizes it aside from scripts.runner.

from __future__ import absolute_import
from __future__ import print_function

from twisted.cred import credentials
from twisted.internet import reactor
from twisted.spread import pb


class UsersClient(object):

    """
    Client set up in buildbot.scripts.runner to send `buildbot user` args
    over a PB connection to perspective_commandline that will execute the
    args on the database.
    """

    def __init__(self, master, username, password, port):
        self.host = master
        self.username = username
        self.password = password
        self.port = int(port)

    def send(self, op, bb_username, bb_password, ids, info):
        f = pb.PBClientFactory()
        d = f.login(credentials.UsernamePassword(self.username, self.password))
        reactor.connectTCP(self.host, self.port, f)

        @d.addCallback
        def call_commandline(remote):
            d = remote.callRemote("commandline", op, bb_username,
                                  bb_password, ids, info)

            @d.addCallback
            def returnAndLose(res):
                remote.broker.transport.loseConnection()
                return res
            return d
        return d
