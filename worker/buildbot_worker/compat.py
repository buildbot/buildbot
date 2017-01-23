# coding=utf-8
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

from __future__ import absolute_import
from __future__ import print_function
from future.utils import text_type

if str != bytes:
    # On Python 3 and higher, str and bytes
    # are not equivalent.  We must use StringIO for
    # doing io on native strings.
    from io import StringIO as NativeStringIO
else:
    # On Python 2 and older, str and bytes
    # are equivalent.  We must use BytesIO for
    # doing io on native strings.
    from io import BytesIO as NativeStringIO


def bytes2NativeString(x, encoding='utf-8'):
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


def unicode2bytes(x, encoding='utf-8'):
    """
    Convert a unicode string to C{bytes}.

    @param x: a unicode string, of type C{unicode} on Python 2,
              or C{str} on Python 3.
    @param encoding: an optional codec, default: 'utf-8'
    @return: a string of type C{bytes}
    """
    if isinstance(x, text_type):
        x = x.encode(encoding)
    return x


__all__ = [
    "NativeStringIO",
    "bytes2NativeString",
    "unicode2bytes"
]
