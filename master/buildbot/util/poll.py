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


from random import randint

from twisted.internet import defer
from twisted.internet import task
from twisted.python import log

_poller_instances = None


class Poller:

    __slots__ = ['fn', 'instance', 'loop', 'started', 'running',
                 'pending', 'stopDeferreds', '_reactor']

    def __init__(self, fn, instance, reactor):
        self.fn = fn
        self.instance = instance
        self.loop = None
        self.started = False
        self.running = False
        self.pending = False
        self.stopDeferreds = []
        self._reactor = reactor

    @defer.inlineCallbacks
    def _run(self, random_delay_min=0, random_delay_max=0):
        self.running = True
        if random_delay_max:
            yield task.deferLater(self._reactor, randint(random_delay_min, random_delay_max),
                                  lambda: None)
        try:
            yield self.fn(self.instance)
        except Exception as e:
            log.err(e, 'while running {}'.format(self.fn))

        self.running = False
        # loop if there's another pending call
        if self.pending:
            self.pending = False
            yield self._run(random_delay_min, random_delay_max)

    def __call__(self):
        if self.started:
            if self.running:
                self.pending = True
            else:
                # terrible hack..
                old_interval = self.loop.interval
                self.loop.interval = 0
                self.loop.reset()
                self.loop.interval = old_interval

    def start(self, interval, now=False, random_delay_min=0, random_delay_max=0):
        assert not self.started
        if not self.loop:
            self.loop = task.LoopingCall(self._run, random_delay_min, random_delay_max)
            self.loop.clock = self._reactor
        stopDeferred = self.loop.start(interval, now=now)

        @stopDeferred.addCallback
        def inform(_):
            self.started = False
            while self.stopDeferreds:
                self.stopDeferreds.pop().callback(None)
        self.started = True

    def stop(self):
        if self.loop and self.loop.running:
            self.loop.stop()
        if self.started:
            d = defer.Deferred()
            self.stopDeferreds.append(d)
            return d
        return defer.succeed(None)


class _Descriptor:
    def __init__(self, fn, attrName):
        self.fn = fn
        self.attrName = attrName

    def __get__(self, instance, cls):
        try:
            poller = getattr(instance, self.attrName)
        except AttributeError:
            poller = Poller(self.fn, instance, instance.master.reactor)
            setattr(instance, self.attrName, poller)
            # track instances when testing
            if _poller_instances is not None:
                _poller_instances.append((instance, self.attrName))
        return poller


def method(fn):
    stateName = "__poll_" + fn.__name__ + "__"
    return _Descriptor(fn, stateName)


def track_poll_methods():
    global _poller_instances
    _poller_instances = []


def reset_poll_methods():
    global _poller_instances
    for instance, attrname in _poller_instances:  # pylint: disable=not-an-iterable
        delattr(instance, attrname)
    _poller_instances = None
