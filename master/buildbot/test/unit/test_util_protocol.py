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

from twisted.trial import unittest

from buildbot.util.protocol import LineProcessProtocol


class FakeLineProcessProtocol(LineProcessProtocol):

    def __init__(self):
        super().__init__()
        self.out_lines = []
        self.err_lines = []

    def outLineReceived(self, line):
        self.out_lines.append(line)

    def errLineReceived(self, line):
        self.err_lines.append(line)


class TestLineProcessProtocol(unittest.TestCase):

    def test_stdout(self):
        p = FakeLineProcessProtocol()
        p.outReceived(b'\nline2\nline3\nli')
        p.outReceived(b'ne4\nli')
        self.assertEqual(p.out_lines, [b'', b'line2', b'line3', b'line4'])
        p.processEnded(0)
        self.assertEqual(p.out_lines, [b'', b'line2', b'line3', b'line4', b'li'])

    def test_stderr(self):
        p = FakeLineProcessProtocol()
        p.errReceived(b'\nline2\nline3\nli')
        p.errReceived(b'ne4\nli')
        self.assertEqual(p.err_lines, [b'', b'line2', b'line3', b'line4'])
        p.processEnded(0)
        self.assertEqual(p.err_lines, [b'', b'line2', b'line3', b'line4', b'li'])
