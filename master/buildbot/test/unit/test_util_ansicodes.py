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

from buildbot.util.ansicodes import parse_ansi_sgr
from twisted.trial import unittest


class TestAnsiCodes(unittest.TestCase):

    def runTest(self, string, expected):
        ret = parse_ansi_sgr(string)
        self.assertEqual(ret, expected)

    def test_ansi0m(self):
        self.runTest("mfoo", ("foo", []))

    def test_ansi1m(self):
        self.runTest("33mfoo", ("foo", ["33"]))

    def test_ansi2m(self):
        self.runTest("1;33mfoo", ("foo", ["1", "33"]))

    def test_ansi5m(self):
        self.runTest("1;2;3;4;33mfoo", ("foo", ["1", "2", "3", "4", "33"]))

    def test_ansi_notm(self):
        self.runTest("33xfoo", ("foo", []))

    def test_ansi_invalid(self):
        self.runTest("<>foo", ("\033[<>foo", []))

    def test_ansi_invalid_start_by_semicolon(self):
        self.runTest(";3m", ("\033[;3m", []))
