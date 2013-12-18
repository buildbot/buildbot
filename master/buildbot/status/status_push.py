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

from __future__ import with_statement


"""Push events to an abstract receiver.

Implements the HTTP receiver."""

import datetime
import os
import urllib
import urlparse

try:
    import simplejson as json
    assert json
except ImportError:
    import json

from buildbot import config
from buildbot.status.base import StatusReceiverMultiService
from buildbot.status.persistent_queue import DiskQueue
from buildbot.status.persistent_queue import IndexedQueue
from buildbot.status.persistent_queue import MemoryQueue
from buildbot.status.persistent_queue import PersistentQueue
from buildbot.status.web.status_json import FilterOut
from twisted.internet import defer
from twisted.internet import reactor
from twisted.python import log
from twisted.web import client


class StatusPush(StatusReceiverMultiService):

    """Event streamer to a abstract channel.

    It uses IQueue to batch push requests and queue the data when
    the receiver is down.
    When a PersistentQueue object is used, the items are saved to disk on master
    shutdown so they can be pushed back when the master is restarted.
    """

    def __init__(self, serverPushCb, queue=None, path=None, filter=True,
                 bufferDelay=1, retryDelay=5, blackList=None):
        """
        @serverPushCb: callback to be used. It receives 'self' as parameter. It
        should call self.queueNextServerPush() when it's done to queue the next
        push. It is guaranteed that the queue is not empty when this function is
        called.
        @queue: a item queue that implements IQueue.
        @path: path to save config.
        @filter: when True (default), removes all "", None, False, [] or {}
        entries.
        @bufferDelay: amount of time events are queued before sending, to
        reduce the number of push requests rate. This is the delay between the
        end of a request to initializing a new one.
        @retryDelay: amount of time between retries when no items were pushed on
        last serverPushCb call.
        @blackList: events that shouldn't be sent.
        """
        StatusReceiverMultiService.__init__(self)

        # Parameters.
        self.watched = []
        self.queue = queue
        if self.queue is None:
            self.queue = MemoryQueue()
        self.queue = IndexedQueue(self.queue)
        self.path = path
        self.filter = filter
        self.bufferDelay = bufferDelay
        self.retryDelay = retryDelay
        if not callable(serverPushCb):
            raise NotImplementedError('Please pass serverPushCb parameter.')

        def hookPushCb():
            # Update the index so we know if the next push succeed or not, don't
            # update the value when the queue is empty.
            if not self.queue.nbItems():
                return defer.succeed(None)
            self.lastIndex = self.queue.getIndex()
            return defer.maybeDeferred(serverPushCb, self)
        self.serverPushCb = hookPushCb
        self.blackList = blackList

        # Other defaults.
        # IDelayedCall object that represents the next queued push.
        self.task = None
        self.stopped = False
        self.lastIndex = -1
        self.state = {}
        self.state['started'] = str(datetime.datetime.utcnow())
        self.state['next_id'] = 1
        self.state['last_id_pushed'] = 0
        # Try to load back the state.
        if self.path and os.path.isdir(self.path):
            state_path = os.path.join(self.path, 'state')
            if os.path.isfile(state_path):
                with open(state_path, 'r') as f:
                    self.state.update(json.load(f))

        if self.queue.nbItems():
            # Last shutdown was not clean, don't wait to send events.
            self.queueNextServerPush()

    def startService(self):
        """Starting up."""
        StatusReceiverMultiService.startService(self)
        self.status = self.parent.getStatus()
        self.status.subscribe(self)
        self.initialPush()

    def wasLastPushSuccessful(self):
        """Returns if the "virtual pointer" in the queue advanced."""
        return self.lastIndex <= self.queue.getIndex()

    @defer.inlineCallbacks
    def queueNextServerPush(self):
        """Queue the next push or call it immediately.

        Called to signal new items are available to be sent or on shutdown.
        A timer should be queued to trigger a network request or the callback
        should be called immediately. If a status push is already queued, ignore
        the current call.

        Returns a Deferred"""
        # Determine the delay.
        if self.wasLastPushSuccessful():
            if self.stopped:
                # Shutting down.
                delay = 0
            else:
                # Normal case.
                delay = self.bufferDelay
        else:
            if self.stopped:
                # Too bad, we can't do anything now, we're shutting down and the
                # receiver is also down. We'll just save the objects to disk.
                return
            else:
                # The server is inaccessible, retry less often.
                delay = self.retryDelay

        # Cleanup a previously queued task if necessary.
        if self.task:
            # Warning: we could be running inside the task.
            if self.task.active():
                # There was already a task queue, don't requeue it, just let it
                # go.
                return
            else:
                if self.task.active():
                    # There was a task queued but it is requested to call it
                    # *right now* so cancel it.
                    self.task.cancel()
                # Otherwise, it was just a stray object.
                self.task = None

        # Do the queue/direct call.
        if delay:
            # Call in delay seconds.
            self.task = reactor.callLater(delay,
                                          lambda: self.serverPushCb().addErrback(
                                              log.err, 'in serverPushCb'))
        elif self.stopped:
            if self.queue.nbItems():
                # Call right now, we're shutting down.
                yield self.serverPushCb()
            return
        else:
            # delay should never be 0.  That can cause Buildbot to spin tightly
            # trying to push events that may not be received well by a status
            # listener.
            log.err('Did not expect delay to be 0, but it is.')
            return

    def stopService(self):
        """Shutting down."""
        self.finalPush()
        self.stopped = True
        if (self.task and self.task.active()):
            # We don't have time to wait, force an immediate call.
            self.task.cancel()
            self.task = None
            d = self.queueNextServerPush()
        elif self.wasLastPushSuccessful():
            d = self.queueNextServerPush()
        else:
            d = defer.succeed(None)

        # We're dying, make sure we save the results.
        self.queue.save()
        if self.path and os.path.isdir(self.path):
            state_path = os.path.join(self.path, 'state')
            with open(state_path, 'w') as f:
                json.dump(self.state, f, sort_keys=True,
                          indent=2)
        # Make sure all Deferreds are called on time and in a sane order.
        defers = filter(None, [d, StatusReceiverMultiService.stopService(self)])
        return defer.DeferredList(defers)

    def disownServiceParent(self):
        """Unsubscribe from watched builders"""
        for w in self.watched:
            w.unsubscribe(self)
        self.status.unsubscribe(self)
        return StatusReceiverMultiService.disownServiceParent(self)

    @defer.inlineCallbacks
    def push(self, event, **objs):
        """Push a new event.

        The new event will be either:
        - Queued in memory to reduce network usage
        - Queued to disk when the sink server is down
        - Pushed (along the other queued items) to the server
        """
        if self.blackList and event in self.blackList:
            return
        # First, generate the packet.
        packet = {}
        packet['id'] = self.state['next_id']
        self.state['next_id'] += 1
        packet['timestamp'] = str(datetime.datetime.utcnow())
        packet['project'] = self.status.getTitle()
        packet['started'] = self.state['started']
        packet['event'] = event
        packet['payload'] = {}
        for obj_name, obj in objs.items():
            if hasattr(obj, 'asDict'):
                obj = obj.asDict()
            if self.filter:
                obj = FilterOut(obj)
            packet['payload'][obj_name] = obj
        self.queue.pushItem(packet)
        if self.task is None or not self.task.active():
            # No task queued since it was probably idle, let's queue a task.
            yield self.queueNextServerPush()

    # Events

    def initialPush(self):
        # Push everything we want to push from the initial configuration.
        d = self.push('start', status=self.status)
        d.addErrback(log.err, 'while pushing status message')

    def finalPush(self):
        d = self.push('shutdown', status=self.status)
        d.addErrback(log.err, 'while pushing status message')

    def requestSubmitted(self, request):
        d = self.push('requestSubmitted', request=request)
        d.addErrback(log.err, 'while pushing status message')

    def requestCancelled(self, builder, request):
        d = self.push('requestCancelled', builder=builder, request=request)
        d.addErrback(log.err, 'while pushing status message')

    def buildsetSubmitted(self, buildset):
        d = self.push('buildsetSubmitted', buildset=buildset)
        d.addErrback(log.err, 'while pushing status message')

    def builderAdded(self, builderName, builder):
        d = self.push('builderAdded', builderName=builderName, builder=builder)
        d.addErrback(log.err, 'while pushing status message')
        self.watched.append(builder)
        return self

    def builderChangedState(self, builderName, state):
        d = self.push('builderChangedState', builderName=builderName, state=state)
        d.addErrback(log.err, 'while pushing status message')

    def buildStarted(self, builderName, build):
        d = self.push('buildStarted', build=build)
        d.addErrback(log.err, 'while pushing status message')
        return self

    def buildETAUpdate(self, build, ETA):
        d = self.push('buildETAUpdate', build=build, ETA=ETA)
        d.addErrback(log.err, 'while pushing status message')

    def stepStarted(self, build, step):
        d = self.push('stepStarted',
                      properties=build.getProperties().asList(),
                      step=step)
        d.addErrback(log.err, 'while pushing status message')

    def stepTextChanged(self, build, step, text):
        d = self.push('stepTextChanged',
                      properties=build.getProperties().asList(),
                      step=step,
                      text=text)
        d.addErrback(log.err, 'while pushing status message')

    def stepText2Changed(self, build, step, text2):
        d = self.push('stepText2Changed',
                      properties=build.getProperties().asList(),
                      step=step,
                      text2=text2)
        d.addErrback(log.err, 'while pushing status message')

    def stepETAUpdate(self, build, step, ETA, expectations):
        d = self.push('stepETAUpdate',
                      properties=build.getProperties().asList(),
                      step=step,
                      ETA=ETA,
                      expectations=expectations)
        d.addErrback(log.err, 'while pushing status message')

    def logStarted(self, build, step, log):
        d = self.push('logStarted',
                      properties=build.getProperties().asList(),
                      step=step)
        d.addErrback(log.err, 'while pushing status message')

    def logFinished(self, build, step, log):
        d = self.push('logFinished',
                      properties=build.getProperties().asList(),
                      step=step)
        d.addErrback(log.err, 'while pushing status message')

    def stepFinished(self, build, step, results):
        d = self.push('stepFinished',
                      properties=build.getProperties().asList(),
                      step=step)
        d.addErrback(log.err, 'while pushing status message')

    def buildFinished(self, builderName, build, results):
        d = self.push('buildFinished', build=build)
        d.addErrback(log.err, 'while pushing status message')

    def builderRemoved(self, builderName):
        d = self.push('buildedRemoved', builderName=builderName)
        d.addErrback(log.err, 'while pushing status message')

    def changeAdded(self, change):
        d = self.push('changeAdded', change=change)
        d.addErrback(log.err, 'while pushing status message')

    def slaveConnected(self, slavename):
        d = self.push('slaveConnected', slave=self.status.getSlave(slavename))
        d.addErrback(log.err, 'while pushing status message')

    def slaveDisconnected(self, slavename):
        d = self.push('slaveDisconnected', slavename=slavename)
        d.addErrback(log.err, 'while pushing status message')

    def slavePaused(self, slavename):
        d = self.push('slavePaused', slavename=slavename)
        d.addErrback(log.err, 'while pushing status message')

    def slaveUnpaused(self, slavename):
        d = self.push('slaveUnpaused', slavename=slavename)
        d.addErrback(log.err, 'while pushing status message')


class HttpStatusPush(StatusPush):

    """Event streamer to a HTTP server."""

    def __init__(self, serverUrl, debug=None, maxMemoryItems=None,
                 maxDiskItems=None, chunkSize=200, maxHttpRequestSize=2 ** 20,
                 extra_post_params=None, **kwargs):
        """
        @serverUrl: Base URL to be used to push events notifications.
        @maxMemoryItems: Maximum number of items to keep queued in memory.
        @maxDiskItems: Maximum number of items to buffer to disk, if 0, doesn't
        use disk at all.
        @debug: Save the json with nice formatting.
        @chunkSize: maximum number of items to send in each at each HTTP POST.
        @maxHttpRequestSize: limits the size of encoded data for AE, the default
        is 1MB.
        """
        if not serverUrl:
            raise config.ConfigErrors(['HttpStatusPush requires a serverUrl'])

        # Parameters.
        self.serverUrl = serverUrl
        self.extra_post_params = extra_post_params or {}
        self.debug = debug
        self.chunkSize = chunkSize
        self.lastPushWasSuccessful = True
        self.maxHttpRequestSize = maxHttpRequestSize
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
        StatusPush.__init__(self, serverPushCb=HttpStatusPush.pushHttp,
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
            params = {'packets': packets}
            params.update(self.extra_post_params)
            data = urllib.urlencode(params)
            if (not self.maxHttpRequestSize or
                    len(data) < self.maxHttpRequestSize):
                return (data, items)

            if chunkSize == 1:
                # This packet is just too large. Drop this packet.
                log.msg("ERROR: packet %s was dropped, too large: %d > %d" %
                        (items[0]['id'], len(data), self.maxHttpRequestSize))
                chunkSize = self.chunkSize
            else:
                # Try with half the packets.
                chunkSize /= 2
                self.queue.insertBackChunk(items)

    def pushHttp(self):
        """Do the HTTP POST to the server."""
        (encoded_packets, items) = self.popChunk()

        def Success(result):
            """Queue up next push."""
            log.msg('Sent %d events to %s' % (len(items), self.serverUrl))
            self.lastPushWasSuccessful = True
            return self.queueNextServerPush()

        def Failure(result):
            """Insert back items not sent and queue up next push."""
            # Server is now down.
            log.msg('Failed to push %d events to %s: %s' %
                    (len(items), self.serverUrl, str(result)))
            self.queue.insertBackChunk(items)
            if self.stopped:
                # Bad timing, was being called on shutdown and the server died
                # on us. Make sure the queue is saved since we just queued back
                # items.
                self.queue.save()
            self.lastPushWasSuccessful = False
            return self.queueNextServerPush()

        # Trigger the HTTP POST request.
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        connection = client.getPage(self.serverUrl,
                                    method='POST',
                                    postdata=encoded_packets,
                                    headers=headers,
                                    agent='buildbot')
        connection.addCallbacks(Success, Failure)
        return connection

# vim: set ts=4 sts=4 sw=4 et:
