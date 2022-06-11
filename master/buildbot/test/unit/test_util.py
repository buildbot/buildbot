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

import datetime
import locale
import os

import mock

from twisted.internet import reactor
from twisted.internet import task
from twisted.trial import unittest

from buildbot import util


class formatInterval(unittest.TestCase):

    def test_zero(self):
        self.assertEqual(util.formatInterval(0), "0 secs")

    def test_seconds_singular(self):
        self.assertEqual(util.formatInterval(1), "1 secs")

    def test_seconds(self):
        self.assertEqual(util.formatInterval(7), "7 secs")

    def test_minutes_one(self):
        self.assertEqual(util.formatInterval(60), "60 secs")

    def test_minutes_over_one(self):
        self.assertEqual(util.formatInterval(61), "1 mins, 1 secs")

    def test_minutes(self):
        self.assertEqual(util.formatInterval(300), "5 mins, 0 secs")

    def test_hours_one(self):
        self.assertEqual(util.formatInterval(3600), "60 mins, 0 secs")

    def test_hours_over_one_sec(self):
        self.assertEqual(util.formatInterval(3601), "1 hrs, 1 secs")

    def test_hours_over_one_min(self):
        self.assertEqual(util.formatInterval(3660), "1 hrs, 60 secs")

    def test_hours(self):
        self.assertEqual(util.formatInterval(7200), "2 hrs, 0 secs")

    def test_mixed(self):
        self.assertEqual(util.formatInterval(7392), "2 hrs, 3 mins, 12 secs")


class TestHumanReadableDelta(unittest.TestCase):

    def test_timeDeltaToHumanReadable(self):
        """
        It will return a human readable time difference.
        """
        result = util.human_readable_delta(1, 1)
        self.assertEqual('super fast', result)

        result = util.human_readable_delta(1, 2)
        self.assertEqual('1 seconds', result)

        result = util.human_readable_delta(1, 61)
        self.assertEqual('1 minutes', result)

        result = util.human_readable_delta(1, 62)
        self.assertEqual('1 minutes, 1 seconds', result)

        result = util.human_readable_delta(1, 60 * 60 + 1)
        self.assertEqual('1 hours', result)

        result = util.human_readable_delta(1, 60 * 60 + 61)
        self.assertEqual('1 hours, 1 minutes', result)

        result = util.human_readable_delta(1, 60 * 60 + 62)
        self.assertEqual('1 hours, 1 minutes, 1 seconds', result)

        result = util.human_readable_delta(1, 24 * 60 * 60 + 1)
        self.assertEqual('1 days', result)

        result = util.human_readable_delta(1, 24 * 60 * 60 + 2)
        self.assertEqual('1 days, 1 seconds', result)


class TestFuzzyInterval(unittest.TestCase):

    def test_moment(self):
        self.assertEqual(util.fuzzyInterval(1), "a moment")

    def test_seconds(self):
        self.assertEqual(util.fuzzyInterval(17), "17 seconds")

    def test_seconds_rounded(self):
        self.assertEqual(util.fuzzyInterval(48), "50 seconds")

    def test_minute(self):
        self.assertEqual(util.fuzzyInterval(58), "a minute")

    def test_minutes(self):
        self.assertEqual(util.fuzzyInterval(3 * 60 + 24), "3 minutes")

    def test_minutes_rounded(self):
        self.assertEqual(util.fuzzyInterval(32 * 60 + 24), "30 minutes")

    def test_hour(self):
        self.assertEqual(util.fuzzyInterval(3600 + 1200), "an hour")

    def test_hours(self):
        self.assertEqual(util.fuzzyInterval(9 * 3600 - 720), "9 hours")

    def test_day(self):
        self.assertEqual(util.fuzzyInterval(32 * 3600 + 124), "a day")

    def test_days(self):
        self.assertEqual(util.fuzzyInterval((19 + 24) * 3600 + 124), "2 days")

    def test_month(self):
        self.assertEqual(util.fuzzyInterval(36 * 24 * 3600 + 124), "a month")

    def test_months(self):
        self.assertEqual(util.fuzzyInterval(86 * 24 * 3600 + 124), "3 months")

    def test_year(self):
        self.assertEqual(util.fuzzyInterval(370 * 24 * 3600), "a year")

    def test_years(self):
        self.assertEqual(util.fuzzyInterval((2 * 365 + 96) * 24 * 3600), "2 years")


class safeTranslate(unittest.TestCase):

    def test_str_good(self):
        self.assertEqual(util.safeTranslate(str("full")), b"full")

    def test_str_bad(self):
        self.assertEqual(util.safeTranslate(str("speed=slow;quality=high")),
                         b"speed_slow_quality_high")

    def test_str_pathological(self):
        # if you needed proof this wasn't for use with sensitive data
        self.assertEqual(util.safeTranslate(str("p\ath\x01ogy")),
                         b"p\ath\x01ogy")  # bad chars still here!

    def test_unicode_good(self):
        self.assertEqual(util.safeTranslate("full"), b"full")

    def test_unicode_bad(self):
        self.assertEqual(util.safeTranslate(str("speed=slow;quality=high")),
                         b"speed_slow_quality_high")

    def test_unicode_pathological(self):
        self.assertEqual(util.safeTranslate("\u0109"),
                         b"\xc4\x89")  # yuck!


class naturalSort(unittest.TestCase):

    def test_alpha(self):
        self.assertEqual(
            util.naturalSort(['x', 'aa', 'ab']),
            ['aa', 'ab', 'x'])

    def test_numeric(self):
        self.assertEqual(
            util.naturalSort(['1', '10', '11', '2', '20']),
            ['1', '2', '10', '11', '20'])

    def test_alphanum(self):
        l1 = 'aa10ab aa1ab aa10aa f a aa3 aa30 aa3a aa30a'.split()
        l2 = 'a aa1ab aa3 aa3a aa10aa aa10ab aa30 aa30a f'.split()
        self.assertEqual(util.naturalSort(l1), l2)


class none_or_str(unittest.TestCase):

    def test_none(self):
        self.assertEqual(util.none_or_str(None), None)

    def test_str(self):
        self.assertEqual(util.none_or_str("hi"), "hi")

    def test_int(self):
        self.assertEqual(util.none_or_str(199), "199")


class TimeFunctions(unittest.TestCase):

    def test_UTC(self):
        self.assertEqual(util.UTC.utcoffset(datetime.datetime.now()),
                         datetime.timedelta(0))
        self.assertEqual(util.UTC.dst(datetime.datetime.now()),
                         datetime.timedelta(0))
        self.assertEqual(util.UTC.tzname(datetime.datetime.utcnow()), "UTC")

    def test_epoch2datetime(self):
        self.assertEqual(util.epoch2datetime(0),
                         datetime.datetime(1970, 1, 1, 0, 0, 0, tzinfo=util.UTC))
        self.assertEqual(util.epoch2datetime(1300000000),
                         datetime.datetime(2011, 3, 13, 7, 6, 40, tzinfo=util.UTC))

    def test_datetime2epoch(self):
        dt = datetime.datetime(1970, 1, 1, 0, 0, 0, tzinfo=util.UTC)
        self.assertEqual(util.datetime2epoch(dt), 0)
        dt = datetime.datetime(2011, 3, 13, 7, 6, 40, tzinfo=util.UTC)
        self.assertEqual(util.datetime2epoch(dt), 1300000000)


class DiffSets(unittest.TestCase):

    def test_empty(self):
        removed, added = util.diffSets(set([]), set([]))
        self.assertEqual((removed, added), (set([]), set([])))

    def test_no_lists(self):
        removed, added = util.diffSets([1, 2], [2, 3])
        self.assertEqual((removed, added), (set([1]), set([3])))

    def test_no_overlap(self):
        removed, added = util.diffSets(set([1, 2]), set([3, 4]))
        self.assertEqual((removed, added), (set([1, 2]), set([3, 4])))

    def test_no_change(self):
        removed, added = util.diffSets(set([1, 2]), set([1, 2]))
        self.assertEqual((removed, added), (set([]), set([])))

    def test_added(self):
        removed, added = util.diffSets(set([1, 2]), set([1, 2, 3]))
        self.assertEqual((removed, added), (set([]), set([3])))

    def test_removed(self):
        removed, added = util.diffSets(set([1, 2]), set([1]))
        self.assertEqual((removed, added), (set([2]), set([])))


class MakeList(unittest.TestCase):

    def test_empty_string(self):
        self.assertEqual(util.makeList(''), [''])

    def test_None(self):
        self.assertEqual(util.makeList(None), [])

    def test_string(self):
        self.assertEqual(util.makeList('hello'), ['hello'])

    def test_unicode(self):
        self.assertEqual(util.makeList('\N{SNOWMAN}'), ['\N{SNOWMAN}'])

    def test_list(self):
        self.assertEqual(util.makeList(['a', 'b']), ['a', 'b'])

    def test_tuple(self):
        self.assertEqual(util.makeList(('a', 'b')), ['a', 'b'])

    def test_copy(self):
        input = ['a', 'b']
        output = util.makeList(input)
        input.append('c')
        self.assertEqual(output, ['a', 'b'])


class Flatten(unittest.TestCase):

    def test_simple(self):
        self.assertEqual(util.flatten([1, 2, 3]), [1, 2, 3])

    def test_deep(self):
        self.assertEqual(util.flatten([[1, 2], 3, [[4]]]),
                         [1, 2, 3, 4])

    # def test_deeply_nested(self):
    #     self.assertEqual(util.flatten([5, [6, (7, 8)]]),
    #                      [5, 6, 7, 8])

    # def test_tuples(self):
    #     self.assertEqual(util.flatten([(1, 2), 3]), [1, 2, 3])

    def test_dict(self):
        d = {'a': [5, 6, 7], 'b': [7, 8, 9]}
        self.assertEqual(util.flatten(d), d)

    def test_string(self):
        self.assertEqual(util.flatten("abc"), "abc")


class Ascii2Unicode(unittest.TestCase):

    def test_unicode(self):
        rv = util.bytes2unicode('\N{SNOWMAN}', encoding='ascii')
        self.assertEqual((rv, type(rv)), ('\N{SNOWMAN}', str))

    def test_ascii(self):
        rv = util.bytes2unicode('abcd', encoding='ascii')
        self.assertEqual((rv, type(rv)), ('abcd', str))

    def test_nonascii(self):
        with self.assertRaises(UnicodeDecodeError):
            util.bytes2unicode(b'a\x85', encoding='ascii')

    def test_None(self):
        self.assertEqual(util.bytes2unicode(None, encoding='ascii'), None)

    def test_bytes2unicode(self):
        rv1 = util.bytes2unicode(b'abcd')
        rv2 = util.bytes2unicode('efgh')

        self.assertEqual(type(rv1), str)
        self.assertEqual(type(rv2), str)


class StringToBoolean(unittest.TestCase):

    def test_it(self):
        stringValues = [
            (b'on', True),
            (b'true', True),
            (b'yes', True),
            (b'1', True),
            (b'off', False),
            (b'false', False),
            (b'no', False),
            (b'0', False),
            (b'ON', True),
            (b'TRUE', True),
            (b'YES', True),
            (b'OFF', False),
            (b'FALSE', False),
            (b'NO', False),
        ]
        for s, b in stringValues:
            self.assertEqual(util.string2boolean(s), b, repr(s))

    def test_ascii(self):
        rv = util.bytes2unicode(b'abcd', encoding='ascii')
        self.assertEqual((rv, type(rv)), ('abcd', str))

    def test_nonascii(self):
        with self.assertRaises(UnicodeDecodeError):
            util.bytes2unicode(b'a\x85', encoding='ascii')

    def test_None(self):
        self.assertEqual(util.bytes2unicode(None, encoding='ascii'), None)


class AsyncSleep(unittest.TestCase):

    def test_sleep(self):
        clock = task.Clock()
        self.patch(reactor, 'callLater', clock.callLater)
        d = util.asyncSleep(2)
        self.assertFalse(d.called)
        clock.advance(1)
        self.assertFalse(d.called)
        clock.advance(1)
        self.assertTrue(d.called)


class FunctionalEnvironment(unittest.TestCase):

    def test_working_locale(self):
        environ = {'LANG': 'en_GB.UTF-8'}
        self.patch(os, 'environ', environ)
        config = mock.Mock()
        util.check_functional_environment(config)
        self.assertEqual(config.error.called, False)

    def test_broken_locale(self):
        def err():
            raise KeyError
        self.patch(locale, 'getdefaultlocale', err)
        config = mock.Mock()
        util.check_functional_environment(config)
        config.error.assert_called_with(mock.ANY)


class StripUrlPassword(unittest.TestCase):

    def test_simple_url(self):
        self.assertEqual(util.stripUrlPassword('http://foo.com/bar'),
                         'http://foo.com/bar')

    def test_username(self):
        self.assertEqual(util.stripUrlPassword('http://d@foo.com/bar'),
                         'http://d@foo.com/bar')

    def test_username_with_at(self):
        self.assertEqual(util.stripUrlPassword('http://d@bb.net@foo.com/bar'),
                         'http://d@bb.net@foo.com/bar')

    def test_username_pass(self):
        self.assertEqual(util.stripUrlPassword('http://d:secret@foo.com/bar'),
                         'http://d:xxxx@foo.com/bar')

    def test_username_pass_with_at(self):
        self.assertEqual(
            util.stripUrlPassword('http://d@bb.net:scrt@foo.com/bar'),
            'http://d@bb.net:xxxx@foo.com/bar')


class JoinList(unittest.TestCase):

    def test_list(self):
        self.assertEqual(util.join_list(['aa', 'bb']), 'aa bb')

    def test_tuple(self):
        self.assertEqual(util.join_list(('aa', 'bb')), 'aa bb')

    def test_string(self):
        self.assertEqual(util.join_list('abc'), 'abc')

    def test_unicode(self):
        self.assertEqual(util.join_list('abc'), 'abc')

    def test_nonascii(self):
        with self.assertRaises(UnicodeDecodeError):
            util.join_list([b'\xff'])


class CommandToString(unittest.TestCase):

    def test_short_string(self):
        self.assertEqual(util.command_to_string("ab cd"), "'ab cd'")

    def test_long_string(self):
        self.assertEqual(util.command_to_string("ab cd ef"), "'ab cd ...'")

    def test_list(self):
        self.assertEqual(util.command_to_string(['ab', 'cd', 'ef']),
                         "'ab cd ...'")

    def test_nested_list(self):
        self.assertEqual(util.command_to_string(['ab', ['cd', ['ef']]]),
                         "'ab cd ...'")

    def test_object(self):
        # this looks like a renderable
        self.assertEqual(util.command_to_string(object()), None)

    def test_list_with_objects(self):
        # the object looks like a renderable, and is skipped
        self.assertEqual(util.command_to_string(['ab', object(), 'cd']),
                         "'ab cd'")

    def test_invalid_ascii(self):
        self.assertEqual(util.command_to_string(b'a\xffc'), "'a\ufffdc'")


class TestRewrap(unittest.TestCase):

    def test_main(self):
        tests = [
            ("", "", None),
            ("\n", "\n", None),
            ("\n  ", "\n", None),
            ("  \n", "\n", None),
            ("  \n  ", "\n", None),
            ("""
                multiline
                with
                indent
                """,
             "\nmultiline with indent",
             None),
            ("""\
                multiline
                with
                indent

                """,
             "multiline with indent\n",
             None),
            ("""\
                 multiline
                 with
                 indent

                 """,
             "multiline with indent\n",
             None),
            ("""\
                multiline
                with
                indent

                  and
                   formatting
                """,
             "multiline with indent\n  and\n   formatting\n",
             None),
            ("""\
                multiline
                with
                indent
                and wrapping

                  and
                   formatting
                """,
             "multiline with\nindent and\nwrapping\n  and\n   formatting\n",
             15),
        ]

        for text, expected, width in tests:
            self.assertEqual(util.rewrap(text, width=width), expected)


class TestMerge(unittest.TestCase):

    def test_merge(self):
        self.assertEqual(
            util.dictionary_merge(
                {
                    'a': {'b': 1}
                },
                {
                    'a': {'c': 2}
                }),
            {
                'a': {'b': 1, 'c': 2}
            })

    def test_overwrite(self):
        self.assertEqual(
            util.dictionary_merge(
                {
                    'a': {'b': 1}
                },
                {
                    'a': 1
                }),
            {
                'a': 1
            })

    def test_overwrite2(self):
        self.assertEqual(
            util.dictionary_merge(
                {
                    'a': {'b': 1, 'c': 2}
                },
                {
                    'a': {'b': [1, 2, 3]}
                }),
            {
                'a': {'b': [1, 2, 3], 'c': 2}
            })
