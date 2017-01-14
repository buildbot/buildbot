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


class TupleMatchingMixin(object):

    # a bunch of tuple-matching tests that all call do_test_match
    # this is used to test this behavior in a few places

    def do_test_match(self, routingKey, shouldMatch, *tuples):
        raise NotImplementedError

    def test_simple_tuple_match(self):
        return self.do_test_match(('abc',), True, ('abc',))

    def test_simple_tuple_no_match(self):
        return self.do_test_match(('abc',), False, ('def',))

    def test_multiple_tuple_match(self):
        return self.do_test_match(('a', 'b', 'c'), True, ('a', 'b', 'c'))

    def test_multiple_tuple_match_tuple_prefix(self):
        return self.do_test_match(('a', 'b', 'c'), False, ('a', 'b'))

    def test_multiple_tuple_match_tuple_suffix(self):
        return self.do_test_match(('a', 'b', 'c'), False, ('b', 'c'))

    def test_multiple_tuple_match_rk_prefix(self):
        return self.do_test_match(('a', 'b'), False, ('a', 'b', 'c'))

    def test_multiple_tuple_match_rk_suffix(self):
        return self.do_test_match(('b', 'c'), False, ('a', 'b', 'c'))

    def test_None_match(self):
        return self.do_test_match(('a', 'b', 'c'), True, ('a', None, 'c'))

    def test_None_match_empty(self):
        return self.do_test_match(('a', '', 'c'), True, ('a', None, 'c'))

    def test_None_no_match(self):
        return self.do_test_match(('a', 'b', 'c'), False, ('a', None, 'x'))
