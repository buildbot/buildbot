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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet.base import _ThreePhaseEvent
from twisted.internet.interfaces import IReactorCore
from twisted.internet.interfaces import IReactorThreads
from twisted.internet.task import Clock
from twisted.python.failure import Failure
from zope.interface import implementer

# The code here is based on the implementations in
# https://twistedmatrix.com/trac/ticket/8295
# https://twistedmatrix.com/trac/ticket/8296


@implementer(IReactorCore)
class CoreReactor(object):

    """
    Partial implementation of ``IReactorCore``.
    """

    def __init__(self):
        self._triggers = {}

    def addSystemEventTrigger(self, phase, eventType, f, *args, **kw):
        event = self._triggers.setdefault(eventType, _ThreePhaseEvent())
        return eventType, event.addTrigger(phase, f, *args, **kw)

    def removeSystemEventTrigger(self, triggerID):
        eventType, handle = triggerID
        event = self._triggers.setdefault(eventType, _ThreePhaseEvent())
        event.removeTrigger(handle)

    def fireSystemEvent(self, eventType):
        event = self._triggers.get(eventType)
        if event is not None:
            event.fireEvent()

    def callWhenRunning(self, f, *args, **kwargs):
        f(*args, **kwargs)


class NonThreadPool(object):

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
        except:  # noqa pylint: disable=bare-except
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
class NonReactor(object):

    """
    A partial implementation of ``IReactorThreads`` which fits into
    the execution model defined by ``NonThreadPool``.
    """

    def callFromThread(self, f, *args, **kwargs):
        f(*args, **kwargs)

    def getThreadPool(self):
        return NonThreadPool()


class TestReactor(NonReactor, CoreReactor, Clock):

    def __init__(self):
        Clock.__init__(self)
        CoreReactor.__init__(self)
