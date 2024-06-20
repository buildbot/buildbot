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

from twisted.python.failure import Failure
from twisted.web.server import Site


class SiteWithClose(Site):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._protocols = []

    def buildProtocol(self, addr):
        p = super().buildProtocol(addr)
        self._protocols.append(p)
        return p

    def close_connections(self):
        for p in self._protocols:
            p.connectionLost(Failure(RuntimeError("Closing down at the end of test")))
            # There is currently no other way to force all pending server-side connections to
            # close.
            p._channel.transport.connectionLost(
                Failure(RuntimeError("Closing down at the end of test"))
            )
        self._protocols = []
