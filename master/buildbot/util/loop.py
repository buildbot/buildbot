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

"""
One-at-a-time notification-triggered Deferred event loop. Each such loop has a
'doorbell' named trigger() and a set of processing functions.  The processing
functions are expected to be callables like Scheduler methods, which examine a
database for work to do. The doorbell will be rung by other code that writes
into the database (possibly in a separate process).

At some point after the doorbell is rung, each function will be run in turn,
one at a time.  Each function can return a Deferred, and the next function will
not be run until the previous one's Deferred has fired.  That is, at all times,
at most one processing function will be active. 

If the doorbell is rung during a run, the loop will be run again later.
Multiple rings may be handled by a single run, but the class guarantees that
there will be at least one full run that begins after the last ring.  The
relative order of processing functions within a run is not preserved.  If a
processing function is added to the loop more than once, it will still only be
called once per run.

If the Deferred returned by the processing function fires with a number, the
event loop will call that function again at or after the given time
(expressed as seconds since epoch). This can be used by processing functions
when they want to 'sleep' until some amount of time has passed, such as for a
Scheduler that is waiting for a tree-stable-timer to expire, or a Periodic
scheduler that wants to fire once every six hours. This delayed call will
obey the same one-at-a-time behavior as the run-everything trigger.

Each function's return-value-timer value will replace the previous timer. Any
outstanding timer will be cancelled just before invoking a processing
function. As a result, these functions should basically be idempotent: if the
database says that the Scheduler needs to wake up at 5pm, it should keep
returning '5pm' until it gets called after 5pm, at which point it should
start returning None.

The functions should also add an epsilon (perhaps one second) to their
desired wakeup time, so that rounding errors or low-resolution system timers
don't cause 'OCD Alarm Clock Syndrome' (in which they get woken up a moment
too early and then try to sleep repeatedly for zero seconds). The event loop
will silently impose a 5-second minimum delay time to avoid this.

Any errors in the processing functions are written to log.err and then
ignored.
"""


from twisted.internet import reactor, defer
from twisted.application import service
from twisted.python import log

from buildbot.util.eventual import eventually
from buildbot import util
from buildbot.process.metrics import Timer, countMethod

class LoopBase(service.MultiService):
    OCD_MINIMUM_DELAY = 5.0

    def __init__(self):
        service.MultiService.__init__(self)
        self._loop_running = False
        self._everything_needs_to_run = False
        self._wakeup_timer = None
        self._timers = {}
        self._when_quiet_waiters = set()
        self._start_timer = None
        self._reactor = reactor # seam for tests to use t.i.t.Clock
        self._remaining = []

    def stopService(self):
        if self._start_timer and self._start_timer.active():
            self._start_timer.cancel()
        if self._wakeup_timer and self._wakeup_timer.active():
            self._wakeup_timer.cancel()
        return service.MultiService.stopService(self)

    def is_quiet(self):
        return not self._loop_running

    def when_quiet(self):
        d = defer.Deferred()
        self._when_quiet_waiters.add(d)
        return d

    def trigger(self):
        # if we're triggered while not running, ignore it.  We'll automatically
        # trigger when the service starts
        if not self.running:
            log.msg("loop triggered while service disabled; ignoring trigger")
            return
        self._mark_runnable(run_everything=True)

    def _mark_runnable(self, run_everything):
        if run_everything:
            self._everything_needs_to_run = True
            # timers are now redundant, so cancel any existing ones
            self._timers.clear()
            self._set_wakeup_timer()
        if self._loop_running:
            return
        self._loop_running = True
        self._start_timer = self._reactor.callLater(0, self._loop_start)

    def get_processors(self):
        raise Exception('subclasses must implement get_processors()')

    _loop_timer = Timer('Loop.run')
    @_loop_timer.startTimer
    @countMethod('Loop._loop_start()')
    def _loop_start(self):
        if self._everything_needs_to_run:
            self._everything_needs_to_run = False
            self._timers.clear()
            self._set_wakeup_timer()
            self._remaining = list(self.get_processors())
        else:
            self._remaining = []
            now = util.now(self._reactor)
            all_processors = self.get_processors()
            for p in list(self._timers.keys()):
                if self._timers[p] <= now:
                    del self._timers[p]
                    # don't run a processor that was removed while it still
                    # had a timer running
                    if p in all_processors:
                        self._remaining.append(p)
                # consider sorting by 'when'
        self._loop_next()

    @countMethod('Loop._loop_next()')
    def _loop_next(self):
        if not self._remaining:
            return self._loop_done()
        p = self._remaining.pop(0)
        self._timers.pop(p, None)
        now = util.now(self._reactor)
        d = defer.maybeDeferred(p)
        d.addCallback(self._set_timer, now, p)
        d.addErrback(log.err)
        d.addBoth(self._one_done)
        return None # no long Deferred chains

    def _one_done(self, ignored):
        eventually(self._loop_next)

    @_loop_timer.stopTimer
    def _loop_done(self):
        if self._everything_needs_to_run:
            self._loop_start()
            return
        self._loop_running = False
        self._set_wakeup_timer()
        if not self._timers:
            # we're really idle, so notify waiters (used by unit tests)
            while self._when_quiet_waiters:
                d = self._when_quiet_waiters.pop()
                self._reactor.callLater(0, d.callback, None)
        self.loop_done()

    def loop_done(self):
        # this can be overridden by subclasses to do more work when we've
        # finished a pass through the loop and don't need to immediately
        # start a new one
        pass

    def _set_timer(self, res, now, p):
        if isinstance(res, (int, float)):
            assert res > now # give me absolute time, not an interval
            # don't wake up right away. By doing this here instead of in
            # _set_wakeup_timer, we avoid penalizing unrelated jobs which
            # want to wake up a few seconds apart
            when = max(res, now+self.OCD_MINIMUM_DELAY)
            self._timers[p] = when

    def _set_wakeup_timer(self):
        if not self._timers:
            if self._wakeup_timer:
                self._wakeup_timer.cancel()
                self._wakeup_timer = None
            return
        when = min(self._timers.values())
        # to avoid waking too frequently, this could be:
        #  delay=max(when-now,OCD_MINIMUM_DELAY)
        # but that delays unrelated jobs that want to wake few seconds apart
        delay = max(0, when - util.now(self._reactor))
        if self._wakeup_timer:
            self._wakeup_timer.reset(delay)
        else:
            self._wakeup_timer = self._reactor.callLater(delay, self._wakeup)

    def _wakeup(self):
        self._wakeup_timer = None
        self._mark_runnable(run_everything=False)

class Loop(LoopBase):
    def __init__(self):
        LoopBase.__init__(self)
        self.processors = set()

    def add(self, processor):
        self.processors.add(processor)

    def remove(self, processor):
        self.processors.remove(processor)

    def get_processors(self):
        return self.processors.copy()

class DelegateLoop(LoopBase):
    def __init__(self, get_processors_function):
        LoopBase.__init__(self)
        self.get_processors = get_processors_function

class MultiServiceLoop(LoopBase):
    """I am a Loop which gets my processors from my service children. When I
    run, I iterate over each of them, invoking their 'run' method."""

    def get_processors(self):
        return [child.run for child in self]
