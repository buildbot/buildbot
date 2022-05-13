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
# Alternatively, you can use and copy this module under the MIT License
# Copyright Buildbot Team Members

import asyncio
import inspect
from asyncio import base_events
from asyncio import events

from twisted.internet import defer


def deferred_await(self):
    # if a deferred is awaited from a asyncio loop context, we must return
    # the future wrapper, but if it is awaited from normal twisted loop
    # we must return self.
    if isinstance(asyncio.get_event_loop(), AsyncIOLoopWithTwisted):
        return self.asFuture(asyncio.get_event_loop())
    return self


defer.Deferred.__await__ = deferred_await


def as_deferred(f):
    return asyncio.get_event_loop().as_deferred(f)


def as_future(d):
    return d.asFuture(asyncio.get_event_loop())


class AsyncIOLoopWithTwisted(base_events.BaseEventLoop):
    """
    Minimal asyncio loop for Buildbot asyncio only dependencies
    as of now, only graphql is needing asyncio loop

    As of now, it can only run basic coroutines, no network operation is supported
    But this could be implemented as needed
    """

    def __init__(self, reactor):
        self._running = False
        self._reactor = reactor
        super().__init__()
        self._running = True

    def start(self):
        self._running = True
        events._set_running_loop(self)

    def stop(self):
        self._running = False
        events._set_running_loop(None)

    def is_running(self):
        return self._running

    def call_soon(self, callback, *args, context=None):
        handle = events.Handle(callback, args, self, context)

        self._reactor.callLater(0, handle._run)
        return handle

    def call_soon_threadsafe(self, callback, *args, context=None):
        handle = events.Handle(callback, args, self, context)

        self._reactor.callFromThread(handle._run)
        return handle

    def time(self):
        # we delegate timekeeping to the reactor so that it can be faked
        return self._reactor.seconds()

    def call_at(self, when, callback, *args, context=None):
        handle = events.Handle(callback, args, self, context)

        # Twisted timers are relatives, contrary to asyncio.
        delay = when - self.time()
        delay = max(delay, 0)
        self._reactor.callLater(delay, handle._run)
        return handle

    def as_deferred(self, thing):
        if isinstance(thing, defer.Deferred):
            return thing

        # check for coroutine objects
        if inspect.isawaitable(thing):
            return defer.Deferred.fromFuture(asyncio.ensure_future(thing))

        return defer.succeed(thing)
