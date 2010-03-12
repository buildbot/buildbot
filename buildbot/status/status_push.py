# -*- test-case-name: buildbot.broken_test.runs.test_status_push -*-

"""Push events to an abstract receiver.

Implements the HTTP receiver."""

import datetime
import os
import urllib
import urlparse

try:
    import simplejson as json
except ImportError:
    import json

from buildbot.master import BuildMaster
from buildbot.status.base import StatusReceiverMultiService
from buildbot.status.persistent_queue import DiskQueue, IQueue, MemoryQueue, \
        PersistentQueue
from buildbot.status.web.status_json import FilterOut
from twisted.internet import defer, reactor
from twisted.python import log
from twisted.web import client


class StatusPush(StatusReceiverMultiService):
    """Event streamer to a abstract channel.

    It uses IQueue to batch network requests and queue the data when
    the server is temporarily down.
    When a PersistentQueue object is used, the items are saved to disk on master
    shutdown so they can be pushed back when the master is restarted.
    """

    def __init__(self, serverPushCb, queue=None, path=None, filter=True,
                 bufferDelay=0.1, retryDelay=1, waterLevel=0):
        """
        @serverPushCb: callback to be used. It should call
        self.queueNextServerPush() when it's done to queue the next push.
        @queue: a item queue that implements IQueue.
        @path: path to save config.
        @filter: when True (default), removes all "", None, False, [] or {}
        entries.
        @bufferDelay: amount of time events are queued before sending, to
        reduce the number of network requests. This is the delay between the end
        of a request to initializing a new one.
        @retryDelay: amount of time between retries when the server is down.
        @waterLevel: number of items that will trigger an immediate retry when
        the server is up. Disabled if 0.
        """
        StatusReceiverMultiService.__init__(self)

        # Parameters.
        self.queue = queue
        if self.queue is None:
            self.queue = MemoryQueue()
        self.path = path
        self.filter = filter
        self.bufferDelay = bufferDelay
        self.retryDelay = retryDelay
        self.waterLevel = waterLevel
        self.serverPushCb = serverPushCb
        self.stopped = False
        assert IQueue.providedBy(self.queue)
        if not callable(self.serverPushCb):
            raise NotImplementedError('Please pass serverPushCb parameter.')

        # Other defaults.

        # IDelayedCall object that represents the next queued push.
        self.task = None
        # When False, self.retryDelay should be used instead of
        # self.bufferDelay.
        self.isServerUp = True
        self.state = {}
        self.state['started'] = str(datetime.datetime.utcnow())
        self.state['next_id'] = 1
        self.state['last_id_pushed'] = 0
        # Try to load back the state.
        if self.path and os.path.isdir(self.path):
            state_path = os.path.join(self.path, 'state')
            if os.path.isfile(state_path):
                self.state.update(json.load(open(state_path, 'r')))

        if self.queue.nbItems():
            # Last shutdown was not clean, don't wait to send events.
            self.queueNextServerPush()

    def setServiceParent(self, parent):
        """Starting up."""
        StatusReceiverMultiService.setServiceParent(self, parent)
        self.status = self.parent.getStatus()
        self.status.subscribe(self)
        self.initialPush()

    def queueNextServerPush(self):
        """Queue the next push or call it immediately.

        Called to signal new items are available to be sent or on shutdown.
        A timer should be queued to trigger a network request or the callback
        should be called immediately. If a status push is already queued, ignore
        the current call."""
        # Determine the delay.
        if self.isServerUp:
            if (self.stopped or
                    (self.waterLevel != 0 and
                        self.queue.nbItems() > self.waterLevel)):
                # Already at high water level so don't wait, we already have
                # enough items to push.
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
            if self.task.active() and delay != 0:
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
            self.task = reactor.callLater(delay, self.serverPushCb)
        elif self.stopped:
            # Call right now, we're shutting down.
            @defer.deferredGenerator
            def BlockForEverythingBeingSent():
                d = self.serverPushCb()
                if d:
                  x = defer.waitForDeferred(d)
                  yield x
                  x.getResult()
            return BlockForEverythingBeingSent()
        else:
            # Call right now, delay == 0.
            return self.serverPushCb()

    def stopService(self):
        """Shutting down."""
        self.finalPush()

        self.stopped = True
        if (self.task and self.task.active()):
            # We don't have time to wait, force an immediate call.
            self.task.cancel()
            self.task = None
        if self.isServerUp:
            d = self.queueNextServerPush()
        else:
            d = defer.succeed(None)

        # We're dying, make sure we save the results.
        self.queue.save()
        if self.path and os.path.isdir(self.path):
            state_path = os.path.join(self.path, 'state')
            json.dump(self.state, open(state_path, 'w'), sort_keys=True,
                      indent=2)
        # Make sure all Deferreds are called on time and in a sane order.
        defers = [d, StatusReceiverMultiService.stopService(self)]
        return defer.DeferredList(defers)

    def push(self, event, **objs):
        """Push a new event.

        The new event will be either:
        - Queued in memory to reduce network usage
        - Queued to disk when the sink server is down
        - Pushed (along the other queued items) to the server
        """
        # First, generate the packet.
        packet = {}
        packet['id'] = self.state['next_id']
        self.state['next_id'] += 1
        packet['timestamp'] = str(datetime.datetime.utcnow())
        packet['project'] = self.status.getProjectName()
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
            self.queueNextServerPush()

    #### Events

    def initialPush(self):
        # Push everything we want to push from the initial configuration.
        self.push('start', status=self.status)

    def finalPush(self):
        self.push('shutdown', status=self.status)

    def requestSubmitted(self, request):
        self.push('requestSubmitted', request=request)

    def requestCancelled(self, builder, request):
        self.push('requestCancelled', builder=builder, request=request)

    def buildsetSubmitted(self, buildset):
        self.push('buildsetSubmitted', buildset=buildset)

    def builderAdded(self, builderName, builder):
        self.push('builderAdded', builderName=builderName, builder=builder)
        return self

    def builderChangedState(self, builderName, state):
        self.push('builderChangedState', builderName=builderName, state=state)

    def buildStarted(self, builderName, build):
        self.push('buildStarted', build=build)
        return self

    def buildETAUpdate(self, build, ETA):
        self.push('buildETAUpdate', build=build, ETA=ETA)

    def stepStarted(self, build, step):
        self.push('stepStarted',
                  properties=build.getProperties().asList(),
                  step=step)

    def stepTextChanged(self, build, step, text):
        self.push('stepTextChanged',
                  properties=build.getProperties().asList(),
                  step=step,
                  text=text)

    def stepText2Changed(self, build, step, text2):
        self.push('stepText2Changed',
                  properties=build.getProperties().asList(),
                  step=step,
                  text2=text2)

    def stepETAUpdate(self, build, step, ETA, expectations):
        self.push('stepETAUpdate',
                  properties=build.getProperties().asList(),
                  step=step,
                  ETA=ETA,
                  expectations=expectations)

    def logStarted(self, build, step, log):
        self.push('logStarted',
                  properties=build.getProperties().asList(),
                  step=step)

    def logFinished(self, build, step, log):
        self.push('logFinished',
                  properties=build.getProperties().asList(),
                  step=step)

    def stepFinished(self, build, step, results):
        self.push('stepFinished',
                  properties=build.getProperties().asList(),
                  step=step)

    def buildFinished(self, builderName, build, results):
        self.push('buildFinished', build=build)

    def builderRemoved(self, builderName):
        self.push('buildedRemoved', builderName=builderName)

    def changeAdded(self, change):
        self.push('changeAdded', change=change)

    def slaveConnected(self, slavename):
        self.push('slaveConnected', slave=self.status.getSlave(slavename))

    def slaveDisconnected(self, slavename):
        self.push('slaveDisconnected', slavename=slavename)


class HttpStatusPush(StatusPush):
    """Event streamer to a HTTP server."""

    def __init__(self, serverUrl, debug=None, maxMemoryItems=None,
                 maxDiskItems=None, chunkSize=200, **kwargs):
        """
        @serverUrl: Base URL to be used to push events notifications.
        @maxMemoryItems: Maximum number of items to keep queued in memory.
        @maxDiskItems: Maximum number of items to buffer to disk, if 0, doesn't
        use disk at all.
        @debug: Save the json with nice formatting.
        @chunkSize: maximum number of items to send in each at each HTTP POST.
        """
        # Parameters.
        self.serverUrl = serverUrl
        self.debug = debug
        self.chunkSize = chunkSize
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

        if not 'waterLevel' in kwargs:
            kwargs['waterLevel'] = 50
        StatusPush.__init__(self, serverPushCb=self.pushHttp, queue=queue,
                            path=path, **kwargs)

    def popChunk(self):
        """Pops items from the pending list.

        They must be queued back on failure."""
        queue = self.queue.popChunk(self.chunkSize)
        if not queue:
            return None
        if self.debug:
            packets = json.dumps(queue, indent=2, sort_keys=True)
        else:
            packets = json.dumps(queue, separators=(',',':'))
        return (urllib.urlencode({'packets': packets}), queue)

    def pushHttp(self):
        """Do the HTTP POST to the server."""
        tmp = self.popChunk()
        if not tmp:
            # Spurious call. Wait for more data before queuing another push.
            return
        encoded_packets = tmp[0]
        queue = tmp[1]

        def Success(result):
            """Queue up next push."""
            log.msg('Sent %d items. %s' % (len(queue), str(result)))
            self.isServerUp = True
            if self.queue.nbItems():
                # If there are items waiting, start another task. Otherwise wait
                # for the next event push.
                # TODO(maruel): Test it works when there are a *lot* of queued
                # items on shutdown.
                self.queueNextServerPush()

        def Failure(result):
            """Insert back items not sent and queue up next push."""
            # Server is now down.
            log.msg('Failed to push %d items to %s: %s' %
                    (len(queue), self.serverUrl, str(result)))
            self.queue.insertBackChunk(queue)
            if self.stopped:
                # Bad timing, was being called on shutdown and the server died
                # on us. Make sure the queue is saved since we just queued back
                # items.
                self.queue.save()
            self.isServerUp = False
            self.queueNextServerPush()

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
