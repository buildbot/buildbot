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

    if isinstance(expected_regexp, basestring):
        expected_regexp = re.compile(expected_regexp)

    if not expected_regexp.search(str(exception)):
        self.fail('"%s" does not match "%s"' %
                  (expected_regexp.pattern, str(exception)))


def _assertRegexpMatches(self, text, regexp, msg=None):
    """
    Asserts that the message matches a regexp.

    This is a simple clone of unittest.TestCase.assertRegexpMatches() method
    introduced in python 2.7. The goal for this function is to behave exactly
    as assertRegexpMatches() in standard library.
    """
    if not re.search(regexp, text):
        if msg is not None:
            self.fail(msg)
        else:
            self.fail('"%s"\n does not match \n"%s"' %
                      (text, regexp))


def patch():
    unittest.TestCase.assertRaisesRegexp = _assertRaisesRegexp
    unittest.TestCase.assertRegexpMatches = _assertRegexpMatches
