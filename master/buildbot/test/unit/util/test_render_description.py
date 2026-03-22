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

from twisted.trial import unittest

from buildbot.util.render_description import render_description


class TestRaml(unittest.TestCase):
    def test_plain(self) -> None:
        self.assertIsNone(render_description("description", None))

    def test_unknown(self) -> None:
        with self.assertRaises(RuntimeError):
            render_description("description", "unknown")

    def test_markdown(self) -> None:
        self.assertEqual(
            render_description("# description\ntext", "markdown"),
            "<h1>description</h1>\n<p>text</p>",
        )
