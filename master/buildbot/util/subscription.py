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


from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any
from typing import Callable

from twisted.internet import defer
from twisted.python import log

from buildbot.util import Notifier

if TYPE_CHECKING:
    from twisted.internet.defer import Deferred
    from twisted.python.failure import Failure


class SubscriptionPoint:
    def __init__(self, name: str) -> None:
        self.name = name
        self.subscriptions: set[Subscription] = set()
        self._unfinished_deliveries: list[Deferred[None] | SubscriptionPoint] = []
        self._unfinished_notifier: Notifier[None] = Notifier()
        self._got_exceptions: list[Exception | Failure] | None = []

    def __str__(self) -> str:
        return f"<SubscriptionPoint '{self.name}'>"

    def subscribe(self, callback: Callable) -> Subscription:
        sub = Subscription(self, callback)
        self.subscriptions.add(sub)
        return sub

    def deliver(self, *args: Any, **kwargs: Any) -> None:
        self._unfinished_deliveries.append(self)
        for sub in list(self.subscriptions):
            try:
                d = sub.callback(*args, **kwargs)
                if isinstance(d, defer.Deferred):
                    self._unfinished_deliveries.append(d)
                    d.addErrback(self._notify_delivery_exception, sub)
                    d.addBoth(self._notify_delivery_finished, d)

            except Exception as e:
                self._notify_delivery_exception(e, sub)

        self._notify_delivery_finished(None, self)

    def waitForDeliveriesToFinish(self) -> Deferred[None]:
        if not self._unfinished_deliveries:
            return defer.succeed(None)
        return self._unfinished_notifier.wait()

    def pop_exceptions(self) -> list[Exception | Failure] | None:
        exceptions = self._got_exceptions
        self._got_exceptions = None  # we no longer expect any exceptions
        return exceptions

    def _unsubscribe(self, subscription: Subscription) -> None:
        self.subscriptions.remove(subscription)

    def _notify_delivery_exception(
        self,
        e: Exception | Failure,
        sub: Subscription,
    ) -> None:
        log.err(e, f'while invoking callback {sub.callback} to {self}')
        if self._got_exceptions is None:
            log.err(
                e,
                'exceptions have already been collected. '
                'This is serious error, please submit a bug report',
            )
            return
        self._got_exceptions.append(e)

    def _notify_delivery_finished(self, _: None, d: SubscriptionPoint | Deferred[None]) -> None:
        self._unfinished_deliveries.remove(d)
        if not self._unfinished_deliveries:
            self._unfinished_notifier.notify(None)


class Subscription:
    def __init__(self, subpt: SubscriptionPoint, callback: Callable) -> None:
        self.subpt = subpt
        self.callback = callback

    def unsubscribe(self) -> None:
        self.subpt._unsubscribe(self)
