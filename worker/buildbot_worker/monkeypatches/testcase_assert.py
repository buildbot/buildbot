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
from future.utils import string_types

import re
import unittest


def _assertRaisesRegexp(self, expected_exception, expected_regexp,
                        callable_obj, *args, **kwds):
    """
    Asserts that the message in a raised exception matches a regexp.

    This is a simple clone of unittest.TestCase.assertRaisesRegexp() method
    introduced in python 2.7. The goal for this function is to behave exactly
    as assertRaisesRegexp() in standard library.
    """
    exception = None
    try:
        callable_obj(*args, **kwds)
    except expected_exception as ex:  # let unexpected exceptions pass through
        exception = ex

    if exception is None:
        self.fail("%s not raised" % str(expected_exception.__name__))

    if isinstance(expected_regexp, string_types):
        expected_regexp = re.compile(expected_regexp)

    if not expected_regexp.search(str(exception)):
        self.fail('"%s" does not match "%s"' %
                  (expected_regexp.pattern, str(exception)))


def patch():
    hasAssertRaisesRegexp = getattr(unittest.TestCase, "assertRaisesRegexp", None)
    hasAssertRaisesRegex = getattr(unittest.TestCase, "assertRaisesRegex", None)
    if not hasAssertRaisesRegexp:
        # Python 2.6
        unittest.TestCase.assertRaisesRegexp = _assertRaisesRegexp
    if not hasAssertRaisesRegex:
        # Python 2.6 and Python 2.7
        unittest.TestCase.assertRaisesRegex = unittest.TestCase.assertRaisesRegexp
