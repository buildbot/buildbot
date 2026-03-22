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

from twisted.internet.interfaces import IAddress
from twisted.internet.interfaces import ITransport
from twisted.protocols import basic
from zope.interface import implementer

from buildbot.util import unicode2bytes


@implementer(IAddress)
class NullAddress:
    "an address for NullTransport"


@implementer(ITransport)
class NullTransport:
    "a do-nothing transport to make NetstringReceiver happy"

    def write(self, data: bytes) -> None:
        raise NotImplementedError

    def writeSequence(self, data: list[bytes]) -> None:  # type: ignore[override]
        raise NotImplementedError

    def loseConnection(self) -> None:
        pass

    def getPeer(self) -> type[NullAddress]:  # type: ignore[override]
        return NullAddress

    def getHost(self) -> type[NullAddress]:  # type: ignore[override]
        return NullAddress


class NetstringParser(basic.NetstringReceiver):
    """
    Adapts the Twisted netstring support (which assumes it is on a socket) to
    work on simple strings, too.  Call the C{feed} method with arbitrary blocks
    of data, and override the C{stringReceived} method to get called for each
    embedded netstring.  The default implementation collects the netstrings in
    the list C{self.strings}.
    """

    def __init__(self) -> None:
        # most of the complexity here is stubbing out the transport code so
        # that Twisted-10.2.0 and higher believes that this is a valid protocol
        self.makeConnection(NullTransport())
        self.strings: list[bytes] = []

    def feed(self, data: str | bytes) -> None:
        data = unicode2bytes(data)
        self.dataReceived(data)
        # dataReceived handles errors unusually quietly!
        if self.brokenPeer:
            raise basic.NetstringParseError

    def stringReceived(self, string: bytes) -> None:
        self.strings.append(string)
