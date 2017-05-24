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
from future.utils import lrange

import datetime
import random

from twisted.trial import unittest

from buildbot.data import base
from buildbot.data import resultspec
from buildbot.data.resultspec import NoneComparator
from buildbot.data.resultspec import ReverseComparator


def mklist(fld, *values):
    if isinstance(fld, tuple):
        return [dict(zip(fld, val)) for val in values]
    return [{fld: val} for val in values]


class Filter(unittest.TestCase):

    def test_eq(self):
        f = resultspec.Filter('num', 'eq', [10])
        self.assertEqual(list(f.apply(mklist('num', 5, 10))),
                         mklist('num', 10))

    def test_eq_plural(self):
        f = resultspec.Filter('num', 'eq', [10, 15, 20])
        self.assertEqual(list(f.apply(mklist('num', 5, 10, 15))),
                         mklist('num', 10, 15))

    def test_ne(self):
        f = resultspec.Filter('num', 'ne', [10])
        self.assertEqual(list(f.apply(mklist('num', 5, 10))),
                         mklist('num', 5))

    def test_ne_plural(self):
        f = resultspec.Filter('num', 'ne', [10, 15, 20])
        self.assertEqual(list(f.apply(mklist('num', 5, 10, 15))),
                         mklist('num', 5))

    def test_lt(self):
        f = resultspec.Filter('num', 'lt', [10])
        self.assertEqual(list(f.apply(mklist('num', 5, 10, 15))),
                         mklist('num', 5))

    def test_le(self):
        f = resultspec.Filter('num', 'le', [10])
        self.assertEqual(list(f.apply(mklist('num', 5, 10, 15))),
                         mklist('num', 5, 10))

    def test_gt(self):
        f = resultspec.Filter('num', 'gt', [10])
        self.assertEqual(list(f.apply(mklist('num', 5, 10, 15))),
                         mklist('num', 15))

    def test_ge(self):
        f = resultspec.Filter('num', 'ge', [10])
        self.assertEqual(list(f.apply(mklist('num', 5, 10, 15))),
                         mklist('num', 10, 15))


class ResultSpec(unittest.TestCase):

    def assertListResultEqual(self, a, b):
        self.assertIsInstance(a, base.ListResult)
        self.assertIsInstance(b, base.ListResult)
        self.assertEqual(a, b)

    def test_apply_None(self):
        self.assertEqual(resultspec.ResultSpec().apply(None), None)

    def test_apply_details_fields(self):
        data = dict(name="clyde", id=14, favcolor="red")
        self.assertEqual(
            resultspec.ResultSpec(fields=['name']).apply(data),
            dict(name="clyde"))
        self.assertEqual(
            resultspec.ResultSpec(fields=['name', 'id']).apply(data),
            dict(name="clyde", id=14))

    def test_apply_collection_fields(self):
        data = mklist(('a', 'b', 'c'),
                      (1, 11, 111),
                      (2, 22, 222))
        self.assertEqual(
            resultspec.ResultSpec(fields=['a']).apply(data),
            mklist('a', 1, 2))
        self.assertEqual(
            resultspec.ResultSpec(fields=['a', 'c']).apply(data),
            mklist(('a', 'c'), (1, 111), (2, 222)))

    def test_apply_ordering(self):
        data = mklist('name', 'albert', 'bruce', 'cedric', 'dwayne')
        exp = mklist('name', 'albert', 'bruce', 'cedric', 'dwayne')
        random.shuffle(data)
        self.assertEqual(
            resultspec.ResultSpec(order=['name']).apply(data),
            exp)
        self.assertEqual(
            resultspec.ResultSpec(order=['-name']).apply(data),
            list(reversed(exp)))

    def test_apply_ordering_multi(self):
        data = mklist(('fn', 'ln'),
                      ('cedric', 'willis'),
                      ('albert', 'engelbert'),
                      ('bruce', 'willis'),
                      ('dwayne', 'montague'))
        exp = base.ListResult(mklist(('fn', 'ln'),
                                     ('albert', 'engelbert'),
                                     ('dwayne', 'montague'),
                                     ('bruce', 'willis'),
                                     ('cedric', 'willis')), total=4)
        random.shuffle(data)
        self.assertListResultEqual(
            resultspec.ResultSpec(order=['ln', 'fn']).apply(data),
            exp)
        exp = base.ListResult(mklist(('fn', 'ln'),
                                     ('cedric', 'willis'),
                                     ('bruce', 'willis'),
                                     ('dwayne', 'montague'),
                                     ('albert', 'engelbert')), total=4)
        self.assertListResultEqual(
            resultspec.ResultSpec(order=['-ln', '-fn']).apply(data),
            exp)

    def test_apply_filter(self):
        data = mklist('name', 'albert', 'bruce', 'cedric', 'dwayne')
        f = resultspec.Filter(field='name', op='gt', values=['bruce'])
        self.assertListResultEqual(
            resultspec.ResultSpec(filters=[f]).apply(data),
            base.ListResult(mklist('name', 'cedric', 'dwayne'), total=2))
        f2 = resultspec.Filter(field='name', op='le', values=['cedric'])
        self.assertListResultEqual(
            resultspec.ResultSpec(filters=[f, f2]).apply(data),
            base.ListResult(mklist('name', 'cedric'), total=1))

    def test_apply_missing_fields(self):
        data = mklist(('fn', 'ln'),
                      ('cedric', 'willis'),
                      ('albert', 'engelbert'),
                      ('bruce', 'willis'),
                      ('dwayne', 'montague'))
        # note that the REST interface catches this with a nicer error message
        self.assertRaises(KeyError, lambda:
                          resultspec.ResultSpec(fields=['fn'], order=['ln']).apply(data))

    def test_sort_null_datetimefields(self):
        data = mklist(('fn', 'ln'),
                      ('albert', datetime.datetime(1, 1, 1)),
                      ('cedric', None))

        exp = mklist(('fn', 'ln'),
                     ('cedric', None),
                     ('albert', datetime.datetime(1, 1, 1)))

        self.assertListResultEqual(
            resultspec.ResultSpec(order=['ln']).apply(data),
            base.ListResult(exp, total=2))

    def do_test_pagination(self, bareList):
        data = mklist('x', *lrange(101, 131))
        if not bareList:
            data = base.ListResult(data)
            data.offset = None
            data.total = len(data)
            data.limit = None
        self.assertListResultEqual(
            resultspec.ResultSpec(offset=0).apply(data),
            base.ListResult(mklist('x', *lrange(101, 131)),
                            offset=0, total=30))
        self.assertListResultEqual(
            resultspec.ResultSpec(offset=10).apply(data),
            base.ListResult(mklist('x', *lrange(111, 131)),
                            offset=10, total=30))
        self.assertListResultEqual(
            resultspec.ResultSpec(offset=10, limit=10).apply(data),
            base.ListResult(mklist('x', *lrange(111, 121)),
                            offset=10, total=30, limit=10))
        self.assertListResultEqual(
            resultspec.ResultSpec(offset=20, limit=15).apply(data),
            base.ListResult(mklist('x', *lrange(121, 131)),
                            offset=20, total=30, limit=15))  # off the end

    def test_pagination_bare_list(self):
        return self.do_test_pagination(bareList=True)

    def test_pagination_ListResult(self):
        return self.do_test_pagination(bareList=False)

    def test_pagination_prepaginated(self):
        data = base.ListResult(mklist('x', *lrange(10, 20)))
        data.offset = 10
        data.total = 30
        data.limit = 10
        self.assertListResultEqual(
            # ResultSpec has its offset/limit fields cleared
            resultspec.ResultSpec().apply(data),
            base.ListResult(mklist('x', *lrange(10, 20)),
                            offset=10, total=30, limit=10))

    def test_pagination_prepaginated_without_clearing_resultspec(self):
        data = base.ListResult(mklist('x', *lrange(10, 20)))
        data.offset = 10
        data.limit = 10
        # ResultSpec does not have its offset/limit fields cleared - this is
        # detected as an assertion failure
        self.assertRaises(AssertionError, lambda:
                          resultspec.ResultSpec(offset=10, limit=20).apply(data))

    def test_endpoint_returns_total_without_applying_filters(self):
        data = base.ListResult(mklist('x', *lrange(10, 20)))
        data.total = 99
        # apply doesn't want to get a total with filters still outstanding
        f = resultspec.Filter(field='x', op='gt', values=[23])
        self.assertRaises(AssertionError, lambda:
                          resultspec.ResultSpec(filters=[f]).apply(data))

    def test_popProperties(self):
        expected = ['prop1', 'prop2']
        rs = resultspec.ResultSpec(properties=[
            resultspec.Property('property', 'eq', expected)
        ])
        self.assertEqual(len(rs.properties), 1)
        self.assertEqual(rs.popProperties(), expected)
        self.assertEqual(len(rs.properties), 0)

    def test_popFilter(self):
        rs = resultspec.ResultSpec(filters=[
            resultspec.Filter('foo', 'eq', [10]),
            resultspec.Filter('foo', 'gt', [5]),
            resultspec.Filter('base', 'ne', [20]),
        ])
        self.assertEqual(rs.popFilter('baz', 'lt'), None)  # no match
        self.assertEqual(rs.popFilter('foo', 'eq'), [10])
        self.assertEqual(len(rs.filters), 2)

    def test_popBooleanFilter(self):
        rs = resultspec.ResultSpec(filters=[
            resultspec.Filter('foo', 'eq', [True]),
            resultspec.Filter('bar', 'ne', [False]),
        ])
        self.assertEqual(rs.popBooleanFilter('foo'), True)
        self.assertEqual(rs.popBooleanFilter('bar'), True)
        self.assertEqual(len(rs.filters), 0)

    def test_popStringFilter(self):
        rs = resultspec.ResultSpec(filters=[
            resultspec.Filter('foo', 'eq', ['foo']),
        ])
        self.assertEqual(rs.popStringFilter('foo'), 'foo')

    def test_popStringFilterSeveral(self):
        rs = resultspec.ResultSpec(filters=[
            resultspec.Filter('foo', 'eq', ['foo', 'bar']),
        ])
        self.assertEqual(rs.popStringFilter('foo'), None)

    def test_popIntegerFilter(self):
        rs = resultspec.ResultSpec(filters=[
            resultspec.Filter('foo', 'eq', ['12']),
        ])
        self.assertEqual(rs.popIntegerFilter('foo'), 12)

    def test_popIntegerFilterSeveral(self):
        rs = resultspec.ResultSpec(filters=[
            resultspec.Filter('foo', 'eq', ['12', '13']),
        ])
        self.assertEqual(rs.popIntegerFilter('foo'), None)

    def test_popIntegerFilterNotInt(self):
        rs = resultspec.ResultSpec(filters=[
            resultspec.Filter('foo', 'eq', ['bar']),
        ])
        self.assertRaises(ValueError, lambda: rs.popIntegerFilter('foo'))

    def test_removeOrder(self):
        rs = resultspec.ResultSpec(order=['foo', '-bar'])
        rs.removeOrder()
        self.assertEqual(rs.order, None)

    def test_popField(self):
        rs = resultspec.ResultSpec(fields=['foo', 'bar'])
        self.assertTrue(rs.popField('foo'))
        self.assertEqual(rs.fields, ['bar'])

    def test_popField_not_present(self):
        rs = resultspec.ResultSpec(fields=['foo', 'bar'])
        self.assertFalse(rs.popField('nosuch'))
        self.assertEqual(rs.fields, ['foo', 'bar'])


class Comparator(unittest.TestCase):
    def test_noneComparator(self):
        self.assertNotEqual(NoneComparator(None),
                            NoneComparator(datetime.datetime(1, 1, 1)))
        self.assertNotEqual(NoneComparator(datetime.datetime(1, 1, 1)),
                            NoneComparator(None))
        self.assertLess(NoneComparator(None),
                        NoneComparator(datetime.datetime(1, 1, 1)))
        self.assertGreater(NoneComparator(datetime.datetime(1, 1, 1)),
                           NoneComparator(None))
        self.assertLess(NoneComparator(datetime.datetime(1, 1, 1)),
                        NoneComparator(datetime.datetime(1, 1, 2)))
        self.assertEqual(NoneComparator(datetime.datetime(1, 1, 1)),
                         NoneComparator(datetime.datetime(1, 1, 1)))
        self.assertGreater(NoneComparator(datetime.datetime(1, 1, 2)),
                           NoneComparator(datetime.datetime(1, 1, 1)))
        self.assertEqual(NoneComparator(None),
                         NoneComparator(None))

    def test_noneComparison(self):
        noneInList = ["z", None, None, "q", "a", None, "v"]
        sortedList = sorted(noneInList, key=lambda x: NoneComparator(x))
        self.assertEqual(sortedList, [None, None, None, "a", "q", "v", "z"])

    def test_reverseComparator(self):
        reverse35 = ReverseComparator(35)
        reverse36 = ReverseComparator(36)
        self.assertEqual(reverse35, reverse35)
        self.assertNotEqual(reverse35, reverse36)
        self.assertLess(reverse36, reverse35)
        self.assertGreater(reverse35, reverse36)
        self.assertLess(reverse36, reverse35)

    def test_reverseComparison(self):
        nums = [1, 2, 3, 4, 5]
        nums.sort(key=lambda x: ReverseComparator(x))
        self.assertEqual(nums, [5, 4, 3, 2, 1])

    def test_reverseComparisonWithNone(self):
        noneInList = ["z", None, None, "q", "a", None, "v"]
        sortedList = sorted(noneInList, key=lambda x: ReverseComparator(NoneComparator(x)))
        self.assertEqual(sortedList, ["z", "v", "q", "a", None, None, None])
