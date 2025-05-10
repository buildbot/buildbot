# Copyright Buildbot Team Members
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

from typing import TYPE_CHECKING
from typing import Generic
from typing import TypeVar

from twisted.internet.defer import Deferred

if TYPE_CHECKING:
    from twisted.python.failure import Failure

_SelfResultT = TypeVar("_SelfResultT")


class Notifier(Generic[_SelfResultT]):
    def __init__(self) -> None:
        self._waiters: list[Deferred[_SelfResultT]] = list()

    def wait(self) -> Deferred[_SelfResultT]:
        d: Deferred[_SelfResultT] = Deferred()
        self._waiters.append(d)
        return d

    def notify(self, result: _SelfResultT | Failure) -> None:
        if self._waiters:
            waiters = self._waiters
            self._waiters = []
            for waiter in waiters:
                waiter.callback(result)

    def __bool__(self):
        return bool(self._waiters)
