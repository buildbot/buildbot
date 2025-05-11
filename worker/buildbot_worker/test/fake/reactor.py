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

from collections.abc import Callable
from collections.abc import Sequence
from typing import TYPE_CHECKING
from typing import Any
from typing import cast

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.base import _ThreePhaseEvent
from twisted.internet.interfaces import IReactorCore
from twisted.internet.interfaces import IReactorThreads
from twisted.internet.task import Clock
from twisted.python import log
from twisted.python.failure import Failure
from zope.interface import implementer

if TYPE_CHECKING:
    from collections.abc import Callable
    from collections.abc import Sequence

if TYPE_CHECKING:
    from typing import Any
    from typing import TypeVar

    from twisted.internet.interfaces import IDelayedCall
    from twisted.internet.interfaces import IReactorTime
    from typing_extensions import ParamSpec

    from buildbot.util.twisted import ThreadPool
    from buildbot_worker.util.twisted import InlineCallbacksType

    _T = TypeVar('_T')
    _P = ParamSpec('_P')


# The code here is based on the implementations in
# https://twistedmatrix.com/trac/ticket/8295
# https://twistedmatrix.com/trac/ticket/8296


@implementer(IReactorCore)
class CoreReactor:
    """
    Partial implementation of ``IReactorCore``.
    """

    def __init__(self) -> None:
        super().__init__()
        self._triggers: dict[str, _ThreePhaseEvent] = {}

    def addSystemEventTrigger(
        self, phase: str, eventType: str, callable: Callable, *args: object, **kw: object
    ) -> Any:
        event = self._triggers.setdefault(eventType, _ThreePhaseEvent())
        return eventType, event.addTrigger(phase, callable, *args, **kw)

    def removeSystemEventTrigger(self, triggerID: tuple[str, Any]) -> None:
        eventType, handle = triggerID
        event = self._triggers.setdefault(eventType, _ThreePhaseEvent())
        event.removeTrigger(handle)

    def fireSystemEvent(self, eventType: str) -> None:
        event = self._triggers.get(eventType)
        if event is not None:
            event.fireEvent()

    def callWhenRunning(self, callable: Callable, *args: object, **kwargs: object) -> Any | None:
        callable(*args, **kwargs)
        return None

    def crash(self) -> None:
        raise NotImplementedError()

    def iterate(self, delay: float = 0) -> None:
        raise NotImplementedError()

    def run(self) -> None:
        raise NotImplementedError()

    def running(self) -> bool:
        raise NotImplementedError()

    def resolve(self, name: str, timeout: Sequence[int]) -> defer.Deferred[str]:  # type: ignore[override]
        raise NotImplementedError()

    def stop(self) -> None:
        raise NotImplementedError()


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

    def __init__(self, **kwargs: Any) -> None:
        pass

    def callInThreadWithCallback(
        self,
        onResult: Callable[[bool, Failure | _T], None],
        func: Callable[_P, _T],
        *args: _P.args,
        **kw: _P.kwargs,
    ) -> None:
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

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


@implementer(IReactorThreads)
class NonReactor:
    """
    A partial implementation of ``IReactorThreads`` which fits into
    the execution model defined by ``NonThreadPool``.
    """

    def suggestThreadPoolSize(self, size: int) -> None:
        # we don't do threads, so this is a no-op
        pass

    def callFromThread(self, callable: Callable, *args: object, **kwargs: object) -> None:
        callable(*args, **kwargs)
        return None

    def callInThread(self, callable: Callable, *args: object, **kwargs: object) -> None:
        callable(*args, **kwargs)
        return None

    def getThreadPool(self) -> ThreadPool:
        return cast("ThreadPool", NonThreadPool())


class TestReactor(NonReactor, CoreReactor, Clock):
    def __init__(self) -> None:
        super().__init__()

        # whether there are calls that should run right now
        self._pendingCurrentCalls = False
        self.stop_called = False

    def _executeCurrentDelayedCalls(self) -> None:
        while self.getDelayedCalls():
            first = sorted(self.getDelayedCalls(), key=lambda a: a.getTime())[0]
            if first.getTime() > self.seconds():
                break
            self.advance(0)

        self._pendingCurrentCalls = False

    @defer.inlineCallbacks
    def _catchPrintExceptions(
        self,
        what: Callable[_P, None | defer.Deferred[None]],
        *a: _P.args,
        **kw: _P.kwargs,
    ) -> InlineCallbacksType[None]:
        try:
            r = what(*a, **kw)
            if isinstance(r, defer.Deferred):
                yield r
        except Exception as e:
            log.msg('Unhandled exception from deferred when doing TestReactor.advance()', e)
            raise

    def callLater(
        self,
        delay: float,
        callable: Callable[..., object],
        *args: object,
        **kw: object,
    ) -> IDelayedCall:
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
        if delay <= 0 and not self._pendingCurrentCalls:
            cast("IReactorTime", reactor).callLater(0, self._executeCurrentDelayedCalls)

        return super().callLater(delay, self._catchPrintExceptions, callable, *args, **kw)

    def stop(self) -> None:
        # first fire pending calls until the current time. Note that the real
        # reactor only advances until the current time in the case of shutdown.
        self.advance(0)

        # then, fire the shutdown event
        self.fireSystemEvent('shutdown')

        self.stop_called = True
