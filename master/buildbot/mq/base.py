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


from twisted.internet import defer
from twisted.python import failure
from twisted.python import log

from buildbot.util import deferwaiter
from buildbot.util import service


class MQBase(service.AsyncService):
    name = 'mq-implementation'

    def __init__(self):
        super().__init__()
        self._deferwaiter = deferwaiter.DeferWaiter()

    async def stopService(self):
        await self._deferwaiter.wait()
        await super().stopService()

    async def waitUntilEvent(self, filter, check_callback):
        d = defer.Deferred()
        buildCompleteConsumer = await self.startConsuming(
            lambda key, value: d.callback((key, value)), filter
        )
        check = await check_callback()
        # we only wait if the check callback return true
        if not check:
            res = await d
        else:
            res = None
        await buildCompleteConsumer.stopConsuming()
        return res

    def invokeQref(self, qref, routingKey, data):
        self._deferwaiter.add(qref.invoke(routingKey, data))


class QueueRef:
    __slots__ = ['callback']

    def __init__(self, callback):
        self.callback = callback

    def invoke(self, routing_key, data):
        # Potentially returns a Deferred
        if not self.callback:
            return None

        try:
            x = self.callback(routing_key, data)
        except Exception:
            log.err(failure.Failure(), f'while invoking {self.callback!r}')
            return None
        if isinstance(x, defer.Deferred):
            x.addErrback(log.err, f'while invoking {self.callback!r}')
        return x

    def stopConsuming(self):
        # This method may return a Deferred.
        # subclasses should set self.callback to None in this method.
        raise NotImplementedError
