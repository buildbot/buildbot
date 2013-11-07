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

from buildbot.util import typechecks
from twisted.python import log
from twisted.trial import unittest


class Tests(unittest.TestCase):

    def doValidationTest(self, fn, good, bad):
        for g in good:
            log.msg('expect %r to be good' % (g,))
            self.assertTrue(fn(g))
        for b in bad:
            log.msg('expect %r to be bad' % (b,))
            self.assertFalse(fn(b))

    def test_isIdentifier(self):
        self.doValidationTest(lambda o: typechecks.isIdentifier(50, o),
                              good=[
                                  u"linux", u"Linux", u"abc123", u"a" * 50,
                              ], bad=[
                                  None, u'', 'linux', u'a/b', u'\N{SNOWMAN}', u"a.b.c.d",
                                  u"a-b_c.d9", 'spaces not allowed', u"a" * 51,
                                  u"123 no initial digits",
                              ])
