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

import warnings

from twisted.trial import unittest

from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.test.util.warnings import ignoreWarning


class SomeWarning(Warning):
    pass


class OtherWarning(Warning):
    pass


class TestWarningsFilter(unittest.TestCase):

    def test_warnigs_caught(self):
        # Assertion is correct.
        with assertProducesWarning(SomeWarning):
            warnings.warn("test", SomeWarning)

    def test_warnigs_caught_num_check(self):
        # Assertion is correct.
        with assertProducesWarnings(SomeWarning, num_warnings=3):
            warnings.warn("1", SomeWarning)
            warnings.warn("2", SomeWarning)
            warnings.warn("3", SomeWarning)

    def test_warnigs_caught_num_check_fail(self):
        def f1():
            with assertProducesWarnings(SomeWarning, num_warnings=2):
                pass
        self.assertRaises(AssertionError, f1)

        def f2():
            with assertProducesWarnings(SomeWarning, num_warnings=2):
                warnings.warn("1", SomeWarning)
        self.assertRaises(AssertionError, f2)

        def f3():
            with assertProducesWarnings(SomeWarning, num_warnings=2):
                warnings.warn("1", SomeWarning)
                warnings.warn("2", SomeWarning)
                warnings.warn("3", SomeWarning)
        self.assertRaises(AssertionError, f3)

    def test_warnigs_caught_pattern_check(self):
        # Assertion is correct.
        with assertProducesWarning(SomeWarning, message_pattern=r"t.st"):
            warnings.warn("The test", SomeWarning)

    def test_warnigs_caught_pattern_check_fail(self):
        def f():
            # Assertion fails.
            with assertProducesWarning(SomeWarning, message_pattern=r"other"):
                warnings.warn("The test", SomeWarning)

        self.assertRaises(AssertionError, f)

    def test_warnigs_caught_patterns_check(self):
        # Assertion is correct.
        with assertProducesWarnings(SomeWarning,
                                    messages_patterns=["1", "2", "3"]):
            warnings.warn("log 1 message", SomeWarning)
            warnings.warn("log 2 message", SomeWarning)
            warnings.warn("log 3 message", SomeWarning)

    def test_warnigs_caught_patterns_check_fails(self):
        def f1():
            # Assertion fails.
            with assertProducesWarnings(SomeWarning,
                                        messages_patterns=["1", "2"]):
                warnings.warn("msg 1", SomeWarning)

        self.assertRaises(AssertionError, f1)

        def f2():
            # Assertion fails.
            with assertProducesWarnings(SomeWarning,
                                        messages_patterns=["1", "2"]):
                warnings.warn("msg 2", SomeWarning)
                warnings.warn("msg 1", SomeWarning)

        self.assertRaises(AssertionError, f2)

        def f3():
            # Assertion fails.
            with assertProducesWarnings(SomeWarning,
                                        messages_patterns=["1", "2"]):
                warnings.warn("msg 1", SomeWarning)
                warnings.warn("msg 2", SomeWarning)
                warnings.warn("msg 3", SomeWarning)

        self.assertRaises(AssertionError, f3)

    def test_no_warnigs_check(self):
        with assertNotProducesWarnings(SomeWarning):
            pass

        with ignoreWarning(OtherWarning):
            with assertNotProducesWarnings(SomeWarning):
                warnings.warn("msg 3", OtherWarning)

    def test_warnigs_filter(self):
        with ignoreWarning(OtherWarning):
            with assertProducesWarnings(SomeWarning,
                                        messages_patterns=["1", "2", "3"]):
                warnings.warn("other", OtherWarning)
                warnings.warn("log 1 message", SomeWarning)
                warnings.warn("other", OtherWarning)
                warnings.warn("log 2 message", SomeWarning)
                warnings.warn("other", OtherWarning)
                warnings.warn("log 3 message", SomeWarning)
                warnings.warn("other", OtherWarning)

    def test_nested_filters(self):
        with assertProducesWarnings(SomeWarning,
                                    messages_patterns=["some 1"]):
            with assertProducesWarnings(OtherWarning,
                                        messages_patterns=["other 1"]):
                warnings.warn("other 1", OtherWarning)
                warnings.warn("some 1", SomeWarning)

    def test_ignore_warnings(self):
        with assertNotProducesWarnings(SomeWarning):
            with ignoreWarning(SomeWarning):
                warnings.warn("some 1", SomeWarning)
