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
# Portions Copyright Buildbot Team Members


from twisted.internet import protocol


class LineBuffer:
    def __init__(self):
        self._buffer = b""

    def add_data(self, data):
        # returns lines that have been processed, if any
        lines = (self._buffer + data).split(b"\n")
        self._buffer = lines.pop(-1)
        for l in lines:
            yield l.rstrip(b"\r")

    def get_trailing_line(self):
        if self._buffer:
            ret = [self._buffer]
            self._buffer = b""
            return ret
        return []


class LineProcessProtocol(protocol.ProcessProtocol):
    def __init__(self):
        self._out_buffer = LineBuffer()
        self._err_buffer = LineBuffer()

    def outReceived(self, data):
        """
        Translates bytes into lines, and calls outLineReceived.
        """
        for line in self._out_buffer.add_data(data):
            self.outLineReceived(line)

    def errReceived(self, data):
        """
        Translates bytes into lines, and calls errLineReceived.
        """
        for line in self._err_buffer.add_data(data):
            self.errLineReceived(line)

    def processEnded(self, reason):
        for line in self._out_buffer.get_trailing_line():
            self.outLineReceived(line)
        for line in self._err_buffer.get_trailing_line():
            self.errLineReceived(line)

    def outLineReceived(self, line):
        """
        Callback to which stdout lines will be sent.
        Any line that is not terminated by a newline will be processed once the next line comes,
        or when processEnded is called.
        """
        raise NotImplementedError

    def errLineReceived(self, line):
        """
        Callback to which stdout lines will be sent.
        Any line that is not terminated by a newline will be processed once the next line comes,
        or when processEnded is called.
        """
        raise NotImplementedError
