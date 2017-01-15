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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet.interfaces import IAddress
from twisted.internet.interfaces import ITransport
from twisted.protocols import basic
from zope.interface import implementer

from buildbot.util import unicode2bytes


@implementer(IAddress)
class NullAddress(object):

    "an address for NullTransport"


@implementer(ITransport)
class NullTransport(object):

    "a do-nothing transport to make NetstringReceiver happy"

    def write(self, data):
        raise NotImplementedError

    def writeSequence(self, data):
        raise NotImplementedError

    def loseConnection(self):
        pass

    def getPeer(self):
        return NullAddress

    def getHost(self):
        return NullAddress


class NetstringParser(basic.NetstringReceiver):

    """
    Adapts the Twisted netstring support (which assumes it is on a socket) to
    work on simple strings, too.  Call the C{feed} method with arbitrary blocks
    of data, and override the C{stringReceived} method to get called for each
    embedded netstring.  The default implementation collects the netstrings in
    the list C{self.strings}.
    """

    def __init__(self):
        # most of the complexity here is stubbing out the transport code so
        # that Twisted-10.2.0 and higher believes that this is a valid protocol
        self.makeConnection(NullTransport())
        self.strings = []

    def feed(self, data):
        data = unicode2bytes(data)
        self.dataReceived(data)
        # dataReceived handles errors unusually quietly!
        if self.brokenPeer:
            raise basic.NetstringParseError

    def stringReceived(self, string):
        self.strings.append(string)
