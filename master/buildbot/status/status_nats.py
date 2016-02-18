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

from buildbot.status.status_push import StatusPush
from buildbot.status.persistent_queue import DiskQueue, MemoryQueue, PersistentQueue
from buildbot import config

from twisted.python import log
import pynats
import urlparse
import json


class NatsStatusPush(StatusPush):
    """Event streamer to a Nats server."""

    def __init__(self, serverUrl, subject="katana", debug=None, maxMemoryItems=None,
                 maxDiskItems=None, chunkSize=200, maxPushSize=2 ** 20, **kwargs):
        """
        @serverUrl: The Nats server to be used to push events notifications to.
        @subject: The subject to use when publishing data
        @maxMemoryItems: Maximum number of items to keep queued in memory.
        @maxDiskItems: Maximum number of items to buffer to disk, if 0, doesn't
        use disk at all.
        @debug: Save the json with nice formatting.
        @chunkSize: maximum number of items to send in each at each PUSH.
        @maxPushSize: limits the size of encoded data for AE, the default
        is 1MB.
        """
        if not serverUrl:
            raise config.ConfigErrors(['NatsStatusPush requires a serverUrl'])

        # Parameters.
        self.serverUrl = serverUrl
        self.debug = debug
        self.chunkSize = chunkSize
        self.lastPushWasSuccessful = True
        self.subject = subject
        self.maxPushSize = maxPushSize
        self.client = None

        if maxDiskItems != 0:
            # The queue directory is determined by the server url.
            path = ('events_' +
                    urlparse.urlparse(self.serverUrl)[1].split(':')[0])
            queue = PersistentQueue(
                        primaryQueue=MemoryQueue(maxItems=maxMemoryItems),
                        secondaryQueue=DiskQueue(path, maxItems=maxDiskItems))
        else:
            path = None
            queue = MemoryQueue(maxItems=maxMemoryItems)

        # Use the unbounded method.
        StatusPush.__init__(self, serverPushCb=NatsStatusPush.pushData,
                            queue=queue, path=path, **kwargs)

    def wasLastPushSuccessful(self):
        return self.lastPushWasSuccessful

    def popChunk(self):
        """Pops items from the pending list.

        They must be queued back on failure."""
        if self.wasLastPushSuccessful():
            chunkSize = self.chunkSize
        else:
            chunkSize = 1

        while True:
            items = self.queue.popChunk(chunkSize)
            newitems = []
            for item in items:
                if hasattr(item, 'asDict'):
                    newitems.append(item.asDict())
                else:
                    newitems.append(item)
            if self.debug:
                packets = json.dumps(newitems, indent=2, sort_keys=True)
            else:
                packets = json.dumps(newitems, separators=(',', ':'))

            data = packets

            if not self.maxPushSize or len(data) < self.maxPushSize:
                return data, items

            if chunkSize == 1:
                # This packet is just too large. Drop this packet.
                log.msg("ERROR: packet %s was dropped, too large: %d > %d" %
                        (items[0]['id'], len(data), self.maxPushSize))
                chunkSize = self.chunkSize
            else:
                # Try with half the packets.
                chunkSize /= 2
                self.queue.insertBackChunk(items)

    def pushData(self):
        """Do the PUSH to the server."""
        (packets, items) = self.popChunk()

        def Success():
            """Queue up next push."""
            log.msg('Sent %d events to %s' % (len(items), self.serverUrl))
            self.lastPushWasSuccessful = True
            return self.queueNextServerPush()

        def Failure(result):
            """Insert back items not sent and queue up next push."""
            # Server is now down.
            log.msg('Failed to push %d events to %s: %s' % (len(items), self.serverUrl, str(result)))
            self.queue.insertBackChunk(items)
            if self.stopped:
                # Bad timing, was being called on shutdown and the server died
                # on us. Make sure the queue is saved since we just queued back
                # items.
                self.queue.save()
            self.lastPushWasSuccessful = False
            return self.queueNextServerPush()

        # Trigger the PUSH
        try:
            if self.client is None:
                self.client = pynats.Connection(self.serverUrl, verbose=True)
                self.client.connect()

            self.client.publish(self.subject, packets)
            Success()
        except pynats.connection.SocketError as e:
            self.client = None
            Failure(e)
