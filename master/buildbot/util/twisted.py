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

from functools import wraps
from typing import TYPE_CHECKING

from twisted.internet import defer

if TYPE_CHECKING:
    from typing import Any
    from typing import Callable
    from typing import Coroutine
    from typing import ParamSpec
    from typing import TypeVar

    _T = TypeVar('_T')
    _P = ParamSpec('_P')


def async_to_deferred(fn: Callable[_P, Coroutine[Any, Any, _T]]):
    @wraps(fn)
    def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> defer.Deferred[_T]:
        try:
            return defer.ensureDeferred(fn(*args, **kwargs))
        except Exception as e:
            return defer.fail(e)

    return wrapper
