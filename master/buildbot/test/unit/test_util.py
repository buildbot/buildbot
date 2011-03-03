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
from twisted.internet import defer

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

class LRUCache(unittest.TestCase):

    def setUp(self):
        self.lru = util.LRUCache(3)
        self.a = "AAA"
        self.b = "BBB"
        self.x = "XXX"
        self.y = "YYY"

    def test_setitem_and_getitem(self):
        self.lru['a'] = self.a
        self.assertTrue(self.lru['a'] is self.a)

    def test_full(self):
        # full, but not to overflowing
        self.lru.add("a", self.a)
        self.lru.add("x", self.x)
        self.lru.add("y", self.y)
        self.assertTrue(self.lru.get('a') is self.a)
        self.assertTrue(self.lru.get('x') is self.x)
        self.assertTrue(self.lru.get('y') is self.y)

    def test_lru_orderByAdd(self):
        # least-recently used should get kicked out
        self.lru.add("a", self.a)
        self.lru.add("b", self.b)
        self.lru.add("x", self.x)
        self.lru.add("y", self.y)
        self.assertEqual((self.lru.get('a'), self.lru.get('b')),
                         (None, self.b))

    def test_lru_usedByGet(self):
        self.lru.add("a", self.a)
        self.lru.add("b", self.b)
        self.lru.add("x", self.x)
        # use a and x, so b gets pushed out of the cache..
        self.lru.get('a')
        self.lru.get('x')
        self.lru.add("y", self.y)
        self.assertEqual((self.lru.get('a'), self.lru.get('b')),
                         (self.a, None))

    def test_lru_usedByAdd(self):
        # least-recently used should get kicked out
        self.lru.add("a", self.a)
        self.lru.add("b", self.b)
        self.lru.add("x", self.x)
        # re-add a and x, so b gets pushed out of the cache (this is a
        # regression test - older code did not mark items as used when they
        # were added)
        self.lru.add("a", self.a)
        self.lru.add("x", self.x)
        self.lru.add("y", self.y)
        self.assertEqual((self.lru.get('a'), self.lru.get('b')),
                         (self.a, None))

    def test_get_falseValue(self):
        # this more of a regression test: it used to be that getting a
        # false value would not move the key up in the LRU list
        self.lru.add("z", 0)
        self.lru.add("a", self.a)
        self.lru.add("b", self.b)
        self.lru.get("z")
        self.lru.add("x", self.x)
        self.assertEqual(self.lru.get("z"), 0)

class none_or_str(unittest.TestCase):

    def test_none(self):
        self.assertEqual(util.none_or_str(None), None)

    def test_str(self):
        self.assertEqual(util.none_or_str("hi"), "hi")

    def test_int(self):
        self.assertEqual(util.none_or_str(199), "199")

class deferredLocked(unittest.TestCase):
    def test_fn(self):
        l = defer.DeferredLock()
        @util.deferredLocked(l)
        def check_locked(arg1, arg2):
            self.assertEqual([l.locked, arg1, arg2], [True, 1, 2])
            return defer.succeed(None)
        d = check_locked(1, 2)
        def check_unlocked(_):
            self.assertFalse(l.locked)
        d.addCallback(check_unlocked)
        return d

    def test_fn_fails(self):
        l = defer.DeferredLock()
        @util.deferredLocked(l)
        def do_fail():
            return defer.fail(RuntimeError("oh noes"))
        d = do_fail()
        def check_unlocked(_):
            self.assertFalse(l.locked)
        d.addCallbacks(lambda _ : self.fail("didn't errback"),
                       lambda _ : self.assertFalse(l.locked))
        return d

    def test_fn_exception(self):
        l = defer.DeferredLock()
        @util.deferredLocked(l)
        def do_fail():
            raise RuntimeError("oh noes")
        d = do_fail()
        def check_unlocked(_):
            self.assertFalse(l.locked)
        d.addCallbacks(lambda _ : self.fail("didn't errback"),
                       lambda _ : self.assertFalse(l.locked))
        return d

    def test_method(self):
        testcase = self
        class C(object):
            @util.deferredLocked('aLock')
            def check_locked(self, arg1, arg2):
                testcase.assertEqual([self.aLock.locked, arg1, arg2], [True, 1, 2])
                return defer.succeed(None)
        obj = C()
        obj.aLock = defer.DeferredLock()
        d = obj.check_locked(1, 2)
        def check_unlocked(_):
            self.assertFalse(obj.aLock.locked)
        d.addCallback(check_unlocked)
        return d
