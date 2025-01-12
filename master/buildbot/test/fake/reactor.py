# Copyright Buildbot Team Members
# Portions copyright 2015-2016 ClusterHQ Inc.
#
# Permission is hereby granted, free of charge, to any person obtaining
# a copy of this software and associated documentation files (the
# "Software"), to deal in the Software without restriction, including
# without limitation the rights to use, copy, modify, merge, publish,
# distribute, sublicense, and/or sell copies of the Software, and to
# permit persons to whom the Software is furnished to do so, subject to
# the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE
# LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION
# WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
from __future__ import annotations

from typing import Any
from typing import Callable
from typing import Sequence

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.base import _ThreePhaseEvent
from twisted.internet.error import ProcessDone
from twisted.internet.interfaces import IReactorCore
from twisted.internet.interfaces import IReactorThreads
from twisted.internet.task import Clock
from twisted.python import log
from twisted.python.failure import Failure
from zope.interface import implementer

from buildbot.util.twisted import async_to_deferred

# The code here is based on the implementations in
# https://twistedmatrix.com/trac/ticket/8295
# https://twistedmatrix.com/trac/ticket/8296


@implementer(IReactorCore)
class CoreReactor:
    """
    Partial implementation of ``IReactorCore``.
    """

    def __init__(self):
        super().__init__()
        self._triggers = {}

    def addSystemEventTrigger(
        self, phase: str, eventType: str, callable: Callable[..., Any], *args, **kw
    ):
        event = self._triggers.setdefault(eventType, _ThreePhaseEvent())
        return eventType, event.addTrigger(phase, callable, *args, **kw)

    def removeSystemEventTrigger(self, triggerID):
        eventType, handle = triggerID
        event = self._triggers.setdefault(eventType, _ThreePhaseEvent())
        event.removeTrigger(handle)

    def fireSystemEvent(self, eventType):
        event = self._triggers.get(eventType)
        if event is not None:
            event.fireEvent()

    def callWhenRunning(self, callable: Callable[..., Any], *args, **kwargs):
        callable(*args, **kwargs)

    def resolve(self, name: str, timeout: Sequence[int]) -> defer.Deferred[str]:  # type: ignore
        # Twisted 24.11 changed the default value of timeout, thus to support
        # both versions typing is disabled
        raise NotImplementedError("resolve() is not implemented in this reactor")

    def stop(self) -> None:
        raise NotImplementedError("stop() is not implemented in this reactor")

    def running(self) -> bool:
        raise NotImplementedError("running() is not implemented in this reactor")

    def crash(self):
        raise NotImplementedError("crash() is not implemented in this reactor")

    def iterate(self, delay=None):
        raise NotImplementedError("iterate() is not implemented in this reactor")

    def run(self):
        raise NotImplementedError("run() is not implemented in this reactor")

    def runUntilCurrent(self):
        raise NotImplementedError("runUntilCurrent() is not implemented in this reactor")


class NonThreadPool:
    """
    A stand-in for ``twisted.python.threadpool.ThreadPool`` so that the
    majority of the test suite does not need to use multithreading.

    This implementation takes the function call which is meant to run in a
    thread pool and runs it synchronously in the calling thread.

    :ivar int calls: The number of calls which have been dispatched to this
        object.
    """

    calls = 0

    def __init__(self, **kwargs):
        pass

    def callInThreadWithCallback(self, onResult, func, *args, **kw):
        self.calls += 1
        try:
            result = func(*args, **kw)
        except:  # noqa: E722
            # We catch *everything* here, since normally this code would be
            # running in a thread, where there is nothing that will catch
            # error.
            onResult(False, Failure())
        else:
            onResult(True, result)

    def start(self):
        pass

    def stop(self):
        pass


@implementer(IReactorThreads)
class NonReactor:
    """
    A partial implementation of ``IReactorThreads`` which fits into
    the execution model defined by ``NonThreadPool``.
    """

    def suggestThreadPoolSize(self, size: int) -> None:
        pass

    def callInThread(self, callable: Callable[..., Any], *args, **kwargs: object) -> None:
        callable(*args, **kwargs)

    def callFromThread(self, callable: Callable[..., Any], *args: object, **kwargs: object) -> None:  # type: ignore[override]
        callable(*args, **kwargs)

    def getThreadPool(self):
        return NonThreadPool()


class ProcessTransport:
    def __init__(self, pid, reactor):
        self.pid = pid
        self.reactor = reactor

    def signalProcess(self, signal):
        self.reactor.process_signalProcess(self.pid, signal)

    def closeChildFD(self, descriptor):
        self.reactor.process_closeChildFD(self.pid, descriptor)


class ProcessReactor:
    def __init__(self):
        super().__init__()
        self._expected_calls = []
        self._processes = {}
        self._next_pid = 0

    def _check_call(self, call):
        function = call["call"]
        if not self._expected_calls:
            raise AssertionError(f"Unexpected call to {function}(): {call!r}")
        expected_call = self._expected_calls.pop(0)
        self.testcase.assertEqual(call, expected_call, f"when calling to {function}()")

    def spawnProcess(
        self,
        processProtocol,
        executable,
        args,
        env=None,
        path=None,
        uid=None,
        gid=None,
        usePTY=False,
        childFDs=None,
    ):
        call = {
            "call": "spawnProcess",
            "executable": executable,
            "args": args,
            "env": env,
            "path": path,
            "uid": uid,
            "gid": gid,
            "usePTY": usePTY,
            "childFDs": childFDs,
        }
        self._check_call(call)

        pid = self._next_pid
        self._next_pid += 1

        self._processes[pid] = processProtocol
        return ProcessTransport(pid, self)

    def process_signalProcess(self, pid, signal):
        call = {
            "call": "signalProcess",
            "pid": pid,
            "signal": signal,
        }
        self._check_call(call)

    def process_closeChildFD(self, pid, descriptor):
        call = {
            "call": "closeChildFD",
            "pid": pid,
            "descriptor": descriptor,
        }
        self._check_call(call)

    def process_done(self, pid, status):
        reason = ProcessDone(status)
        self._processes[pid].processEnded(reason)
        self._processes[pid].processExited(reason)

    def process_send_stdout(self, pid, data):
        self._processes[pid].outReceived(data)

    def process_send_stderr(self, pid, data):
        self._processes[pid].errReceived(data)

    def assert_no_remaining_calls(self):
        if self._expected_calls:
            msg = "The following expected calls are missing: "
            for call in self._expected_calls:
                copy = call.copy()
                name = copy.pop("call")
                msg += f"\nTo {name}(): {call!r}"
            raise AssertionError(msg)

    def expect_spawn(
        self, executable, args, env=None, path=None, uid=None, gid=None, usePTY=False, childFDs=None
    ):
        self._expected_calls.append({
            "call": "spawnProcess",
            "executable": executable,
            "args": args,
            "env": env,
            "path": path,
            "uid": uid,
            "gid": gid,
            "usePTY": usePTY,
            "childFDs": childFDs,
        })

    def expect_process_signalProcess(self, pid, signal):
        self._expected_calls.append({
            "call": "signalProcess",
            "pid": pid,
            "signal": signal,
        })

    def expect_process_closeChildFD(self, pid, descriptor):
        self._expected_calls.append({
            "call": "closeChildFD",
            "pid": pid,
            "descriptor": descriptor,
        })


class TestReactor(ProcessReactor, NonReactor, CoreReactor, Clock):
    def __init__(self):
        super().__init__()

        # whether there are calls that should run right now
        self._pendingCurrentCalls = False
        self.stop_called = False

    def set_test_case(self, testcase):
        self.testcase = testcase

    def _executeCurrentDelayedCalls(self):
        while self.getDelayedCalls():
            first = sorted(self.getDelayedCalls(), key=lambda a: a.getTime())[0]
            if first.getTime() > self.seconds():
                break
            self.advance(0)

        self._pendingCurrentCalls = False

    @async_to_deferred
    async def _catchPrintExceptions(self, what, *a, **kw) -> None:
        try:
            await defer.maybeDeferred(what, *a, **kw)
        except Exception as e:
            log.msg('Unhandled exception from deferred when doing TestReactor.advance()', e)
            raise

    def callLater(self, when, what, *a, **kw):
        # Buildbot often uses callLater(0, ...) to defer execution of certain
        # code to the next iteration of the reactor. This means that often
        # there are pending callbacks registered to the reactor that might
        # block other code from proceeding unless the test reactor has an
        # iteration. To avoid deadlocks in tests we give the real reactor a
        # chance to advance the test reactor whenever we detect that there
        # are callbacks that should run in the next iteration of the test
        # reactor.
        #
        # Additionally, we wrap all calls with a function that prints any
        # unhandled exceptions
        if when <= 0 and not self._pendingCurrentCalls:
            reactor.callLater(0, self._executeCurrentDelayedCalls)

        return super().callLater(when, self._catchPrintExceptions, what, *a, **kw)

    def stop(self):
        # first fire pending calls until the current time. Note that the real
        # reactor only advances until the current time in the case of shutdown.
        self.advance(0)

        # then, fire the shutdown event
        self.fireSystemEvent('shutdown')

        self.stop_called = True
