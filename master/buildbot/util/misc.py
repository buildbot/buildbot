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
Miscellaneous utilities; these should be imported from C{buildbot.util}, not
directly from this module.
"""

from __future__ import annotations

import os
from functools import wraps
from typing import TYPE_CHECKING

from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.defer import DeferredLock

if TYPE_CHECKING:
    from typing import Callable
    from typing import TypeVar

    from typing_extensions import ParamSpec

    _T = TypeVar('_T')
    _P = ParamSpec('_P')


def deferredLocked(
    lock_or_attr: str | DeferredLock,
) -> Callable[[Callable[_P, Deferred[_T]]], Callable[_P, Deferred[_T]]]:
    def decorator(fn: Callable[_P, Deferred[_T]]) -> Callable[_P, Deferred[_T]]:
        @wraps(fn)
        def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> Deferred[_T]:
            if isinstance(lock_or_attr, str):
                lock = getattr(args[0], lock_or_attr)
                assert isinstance(lock, DeferredLock)
            else:
                lock = lock_or_attr
            return lock.run(fn, *args, **kwargs)

        return wrapper

    return decorator


def cancelAfter(seconds, deferred, _reactor=reactor):
    delayedCall = _reactor.callLater(seconds, deferred.cancel)

    # cancel the delayedCall when the underlying deferred fires
    @deferred.addBoth
    def cancelTimer(x):
        if delayedCall.active():
            delayedCall.cancel()
        return x

    return deferred


def writeLocalFile(path, contents, mode=None):  # pragma: no cover
    with open(path, 'w', encoding='utf-8') as file:
        if mode is not None:
            os.chmod(path, mode)
        file.write(contents)


def chunkify_list(l, chunk_size):
    chunk_size = max(1, chunk_size)
    return (l[i : i + chunk_size] for i in range(0, len(l), chunk_size))
