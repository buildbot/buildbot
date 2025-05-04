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

import itertools
import textwrap
import time
from typing import TYPE_CHECKING
from typing import Generic
from typing import TypeVar
from typing import Union
from typing import overload

from ._hangcheck import HangCheckFactory
from ._notifier import Notifier

if TYPE_CHECKING:
    from typing import Any

    from twisted.internet.interfaces import IReactorTime

    _T = TypeVar('_T')

StrOrBytesType = TypeVar("StrOrBytesType", bound=Union[str, bytes])


__all__ = [
    "HangCheckFactory",
    "Notifier",
    "Obfuscated",
    "now",
    "remove_userpassword",
    "rewrap",
]


def remove_userpassword(url: str) -> str:
    if '@' not in url:
        return url
    if '://' not in url:
        return url

    # urlparse would've been nice, but doesn't support ssh... sigh
    (protocol, repo_url) = url.split('://')
    repo_url = repo_url.split('@')[-1]

    return protocol + '://' + repo_url


def now(_reactor: IReactorTime | None = None) -> float:
    if _reactor is not None and hasattr(_reactor, "seconds"):
        return _reactor.seconds()
    return time.time()


class Obfuscated(Generic[StrOrBytesType]):
    """An obfuscated string in a command"""

    def __init__(self, real: StrOrBytesType, fake: StrOrBytesType) -> None:
        self.real = real
        self.fake = fake

    def __str__(self) -> str:
        return str(self.fake)

    def __repr__(self) -> str:
        return repr(self.fake)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return False
        return (
            other.__class__ is self.__class__
            and other.real == self.real
            and other.fake == self.fake
        )

    @overload
    @staticmethod
    def to_text(s: bytes) -> bytes: ...

    @overload
    @staticmethod
    def to_text(s: Any) -> str: ...

    @staticmethod
    def to_text(s: Any) -> str | bytes:
        if isinstance(s, (str, bytes)):
            return s
        return str(s)

    @overload
    @staticmethod
    def get_real(command: list[Obfuscated | _T]) -> list[str | _T]: ...

    @overload
    @staticmethod
    def get_real(command: _T) -> _T: ...

    @staticmethod
    def get_real(command: list[Obfuscated | Any] | Any) -> list[Any] | Any:
        rv = command
        if isinstance(command, list):
            rv = []
            for elt in command:
                if isinstance(elt, Obfuscated):
                    rv.append(elt.real)
                else:
                    rv.append(Obfuscated.to_text(elt))
        return rv

    @overload
    @staticmethod
    def get_fake(command: list[Obfuscated | _T]) -> list[str | _T]: ...

    @overload
    @staticmethod
    def get_fake(command: _T) -> _T: ...

    @staticmethod
    def get_fake(command: list[Obfuscated | Any] | Any) -> list[Any] | Any:
        rv = command
        if isinstance(command, list):
            rv = []
            for elt in command:
                if isinstance(elt, Obfuscated):
                    rv.append(elt.fake)
                else:
                    rv.append(Obfuscated.to_text(elt))
        return rv


def rewrap(text: str, width: int | None = None) -> str:
    """
    Rewrap text for output to the console.

    Removes common indentation and rewraps paragraphs according to the console
    width.

    Line feeds between paragraphs preserved.
    Formatting of paragraphs that starts with additional indentation
    preserved.
    """

    if width is None:
        width = 80

    # Remove common indentation.
    text = textwrap.dedent(text)

    def needs_wrapping(line: str) -> bool:
        # Line always non-empty.
        return not line[0].isspace()

    # Split text by lines and group lines that comprise paragraphs.
    wrapped_text = ""
    for do_wrap, lines in itertools.groupby(text.splitlines(True), key=needs_wrapping):
        paragraph = ''.join(lines)

        if do_wrap:
            paragraph = textwrap.fill(paragraph, width)

        wrapped_text += paragraph

    return wrapped_text


def twisted_connection_string_to_ws_url(description: str) -> str:
    from twisted.internet.endpoints import _parse

    args, kwargs = _parse(description)
    protocol = args.pop(0).upper()

    host = kwargs.get('host', None)
    port = kwargs.get('port', None)

    if protocol == 'TCP':
        port = kwargs.get('port', 80)

        if len(args) == 2:
            host = args[0]
            port = args[1]
        elif len(args) == 1:
            if "host" in kwargs:
                host = kwargs['host']
                port = args[0]
            else:
                host = args[0]
                port = kwargs.get('port', port)

    if host is None or host == '' or port is None:
        raise ValueError('Host and port must be specified in connection string')

    return f"ws://{host}:{port}"
