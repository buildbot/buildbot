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
Helpers for handling compatibility differences
between Python 2 and Python 3.
"""

from __future__ import annotations

from io import StringIO as NativeStringIO
from typing import TYPE_CHECKING
from typing import overload

if TYPE_CHECKING:
    from typing import Any
    from typing import TypeVar

    _T = TypeVar('_T')


@overload
def bytes2NativeString(x: bytes, encoding: str = 'utf-8') -> str: ...


@overload
def bytes2NativeString(x: _T, encoding: str = 'utf-8') -> _T: ...


def bytes2NativeString(x: _T, encoding: str = 'utf-8') -> str | _T:
    """
    Convert C{bytes} to a native C{str}.

    On Python 3 and higher, str and bytes
    are not equivalent.  In this case, decode
    the bytes, and return a native string.

    On Python 2 and lower, str and bytes
    are equivalent.  In this case, just
    just return the native string.

    @param x: a string of type C{bytes}
    @param encoding: an optional codec, default: 'utf-8'
    @return: a string of type C{str}
    """
    if isinstance(x, bytes) and str != bytes:
        return x.decode(encoding)
    return x


@overload
def unicode2bytes(x: str, encoding: str = 'utf-8', errors: str = 'strict') -> bytes: ...


@overload
def unicode2bytes(x: _T, encoding: str = 'utf-8', errors: str = 'strict') -> _T: ...


def unicode2bytes(x: str | _T, encoding: str = 'utf-8', errors: str = 'strict') -> bytes | _T:
    """
    Convert a unicode string to C{bytes}.

    @param x: a unicode string, of type C{str}.
    @param encoding: an optional codec, default: 'utf-8'
    @param errors: error handling scheme, default 'strict'
    @return: a string of type C{bytes}
    """
    if isinstance(x, str):
        return x.encode(encoding, errors)
    return x


@overload
def bytes2unicode(x: None, encoding: str = 'utf-8', errors: str = 'strict') -> None: ...


@overload
def bytes2unicode(x: Any, encoding: str = 'utf-8', errors: str = 'strict') -> str: ...


def bytes2unicode(x: Any | None, encoding: str = 'utf-8', errors: str = 'strict') -> str | None:
    """
    Convert a C{bytes} to a unicode string.

    @param x: a unicode string, of type C{str}.
    @param encoding: an optional codec, default: 'utf-8'
    @param errors: error handling scheme, default 'strict'
    @return: a unicode string of type C{unicode} on Python 2, or
             C{str} on Python 3.
    """
    if x is None:
        return None
    if isinstance(x, str):
        return x
    return str(x, encoding, errors)


__all__ = ["NativeStringIO", "bytes2NativeString", "bytes2unicode", "unicode2bytes"]
