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

from twisted.python.failure import Failure
from twisted.web.http import _GenericHTTPChannelProtocol
from twisted.web.server import Site

if TYPE_CHECKING:
    from twisted.internet.interfaces import IAddress
    from twisted.internet.protocol import Protocol


class SiteWithClose(Site):
    def __init__(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)

        self._protocols: list[Protocol | None] = []

    def buildProtocol(self, addr: IAddress) -> Protocol | None:
        p = super().buildProtocol(addr)
        self._protocols.append(p)
        return p

    def close_connections(self) -> None:
        for p in self._protocols:
            assert p is not None
            p.connectionLost(Failure(RuntimeError("Closing down at the end of test")))
            # There is currently no other way to force all pending server-side connections to
            # close.
            assert isinstance(p, _GenericHTTPChannelProtocol)
            assert p._channel.transport is not None

            p._channel.transport.connectionLost(
                Failure(RuntimeError("Closing down at the end of test"))
            )
        self._protocols = []
