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

class safeTranslate(unittest.TestCase):

    def test_str_good(self):
        self.assertEqual(util.safeTranslate(str("full")), str("full"))

    def test_str_bad(self):
        self.assertEqual(util.safeTranslate(str("speed=slow;quality=high")),
                         str("speed_slow_quality_high"))

    def test_str_pathological(self):
        # if you needed proof this wasn't for use with sensitive data
        self.assertEqual(util.safeTranslate(str("p\ath\x01ogy")),
                         str("p\ath\x01ogy")) # bad chars still here!

    def test_unicode_good(self):
        self.assertEqual(util.safeTranslate(u"full"), str("full"))

    def test_unicode_bad(self):
        self.assertEqual(util.safeTranslate(unicode("speed=slow;quality=high")),
                         str("speed_slow_quality_high"))

    def test_unicode_pathological(self):
        self.assertEqual(util.safeTranslate(u"\u0109"),
                         str("\xc4\x89")) # yuck!

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
        self.assertEqual(util.UTC.tzname(), "UTC")

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
