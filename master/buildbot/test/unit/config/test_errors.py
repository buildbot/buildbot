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

from buildbot.config.errors import ConfigErrors
from buildbot.config.errors import capture_config_errors
from buildbot.config.errors import error


class ConfigErrorsTest(unittest.TestCase):
    def test_constr(self):
        ex = ConfigErrors(["a", "b"])
        self.assertEqual(ex.errors, ["a", "b"])

    def test_addError(self):
        ex = ConfigErrors(["a"])
        ex.addError("c")
        self.assertEqual(ex.errors, ["a", "c"])

    def test_nonempty(self):
        empty = ConfigErrors()
        full = ConfigErrors(["a"])
        self.assertTrue(not empty)
        self.assertFalse(not full)

    def test_error_raises(self):
        with self.assertRaises(ConfigErrors) as e:
            error("message")
        self.assertEqual(e.exception.errors, ["message"])

    def test_error_no_raise(self):
        with capture_config_errors() as errors:
            error("message")
        self.assertEqual(errors.errors, ["message"])

    def test_str(self):
        ex = ConfigErrors()
        self.assertEqual(str(ex), "")

        ex = ConfigErrors(["a"])
        self.assertEqual(str(ex), "a")

        ex = ConfigErrors(["a", "b"])
        self.assertEqual(str(ex), "a\nb")

        ex = ConfigErrors(["a"])
        ex.addError("c")
        self.assertEqual(str(ex), "a\nc")
