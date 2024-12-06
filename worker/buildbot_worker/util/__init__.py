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

import itertools
import textwrap
import time

from ._hangcheck import HangCheckFactory
from ._notifier import Notifier

__all__ = [
    "remove_userpassword",
    "now",
    "Obfuscated",
    "rewrap",
    "HangCheckFactory",
    "Notifier",
]


def remove_userpassword(url):
    if '@' not in url:
        return url
    if '://' not in url:
        return url

    # urlparse would've been nice, but doesn't support ssh... sigh
    (protocol, repo_url) = url.split('://')
    repo_url = repo_url.split('@')[-1]

    return protocol + '://' + repo_url


def now(_reactor=None):
    if _reactor and hasattr(_reactor, "seconds"):
        return _reactor.seconds()
    return time.time()


class Obfuscated:
    """An obfuscated string in a command"""

    def __init__(self, real, fake):
        self.real = real
        self.fake = fake

    def __str__(self):
        return self.fake

    def __repr__(self):
        return repr(self.fake)

    def __eq__(self, other):
        return (
            other.__class__ is self.__class__
            and other.real == self.real
            and other.fake == self.fake
        )

    @staticmethod
    def to_text(s):
        if isinstance(s, (str, bytes)):
            return s
        return str(s)

    @staticmethod
    def get_real(command):
        rv = command
        if isinstance(command, list):
            rv = []
            for elt in command:
                if isinstance(elt, Obfuscated):
                    rv.append(elt.real)
                else:
                    rv.append(Obfuscated.to_text(elt))
        return rv

    @staticmethod
    def get_fake(command):
        rv = command
        if isinstance(command, list):
            rv = []
            for elt in command:
                if isinstance(elt, Obfuscated):
                    rv.append(elt.fake)
                else:
                    rv.append(Obfuscated.to_text(elt))
        return rv


def rewrap(text, width=None):
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

    def needs_wrapping(line):
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


def twisted_connection_string_to_ws_url(description):
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
