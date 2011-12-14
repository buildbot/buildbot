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

from twisted.internet import reactor

from . import ComparableMixin


class GerritConnectionFactory(ComparableMixin):
    """Contains logic needed to connect to a gerrit code review service."""

    compare_attrs = ["gerrit_server", "gerrit_port"]

    def __init__(self, process_protocol, gerrit_server, gerrit_username,
                 gerrit_port=29418, identity_file=None):
        """
        @type  gerrit_server: string
        @param gerrit_server: the dns or ip that host the gerrit ssh server,

        @type  gerrit_port: int
        @param gerrit_port: the port of the gerrit ssh server,

        @type  gerrit_username: string
        @param gerrit_username: the username to use to connect to gerrit,

        @type  identity_file: string
        @param identity_file: identity file to for authentication (optional).

        """
        self.gerrit_server = gerrit_server
        self.gerrit_username = gerrit_username
        self.gerrit_port = gerrit_port
        self.identity_file = identity_file
        self.process_protocol = process_protocol

        self.command_root = ["ssh", self.gerrit_username + "@" + gerrit_server,
                             "-p", str(self.gerrit_port)]
        if self.identity_file is not None:
            command_root.extend(["-i", self.identity_file])

    def connect(self, gerrit_command):
        args = self.command_root + gerrit_command
        return reactor.spawnProcess(self.process_protocol, "ssh", args)
