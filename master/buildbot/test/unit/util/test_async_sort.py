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


from twisted.internet import defer
from twisted.python import log
from twisted.trial import unittest

from buildbot.test.util.logging import LoggingMixin
from buildbot.util.async_sort import async_sort


class AsyncSort(unittest.TestCase, LoggingMixin):

    def setUp(self) -> None:
        self.setUpLogging()
        return super().setUp()

    @defer.inlineCallbacks
    def test_sync_call(self):
        l = ["b", "c", "a"]
        yield async_sort(l, lambda x: x)
        return self.assertEqual(l, ["a", "b", "c"])

    @defer.inlineCallbacks
    def test_async_call(self):
        l = ["b", "c", "a"]
        yield async_sort(l, defer.succeed)
        self.assertEqual(l, ["a", "b", "c"])

    @defer.inlineCallbacks
    def test_async_fail(self):
        l = ["b", "c", "a"]
        self.patch(log, "err", lambda f: None)

        class SortFail(Exception):
            pass
        with self.assertRaises(SortFail):
            yield async_sort(l, lambda x:
                defer.succeed(x) if x != "a" else defer.fail(SortFail("ono")))

        self.assertEqual(len(self.flushLoggedErrors(SortFail)), 1)
        self.assertEqual(l, ["b", "c", "a"])
