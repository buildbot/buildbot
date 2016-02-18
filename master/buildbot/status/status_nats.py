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


"""Push events to nats

."""

from buildbot import config
import pynats

from buildbot.status.status_queue import QueuedStatusPush


class NatsStatusPush(QueuedStatusPush):
    """Event streamer to a Nats server."""

    def __init__(self, serverUrl, subject="katana", **kwargs):
        """
        @serverUrl: The Nats server to be used to push events notifications to.
        @subject: The subject to use when publishing data
        """
        if not serverUrl:
            raise config.ConfigErrors(['NatsStatusPush requires a serverUrl'])

        # Parameters.
        self.serverUrl = serverUrl
        self.subject = subject
        self.client = None

        # Use the unbounded method.
        QueuedStatusPush.__init__(self, **kwargs)

    def pushData(self, packets):
        try:
            if self.client is None:
                self.client = pynats.Connection(self.serverUrl, verbose=True)
                self.client.connect()

            self.client.publish(self.subject, packets)
            return True, None
        except pynats.connection.SocketError as e:
            self.client = None
            return False, e
