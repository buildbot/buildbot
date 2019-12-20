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
from twisted.trial import unittest

from buildbot.util.deferwaiter import DeferWaiter


class TestException(Exception):
    pass


class Tests(unittest.TestCase):

    def test_add_deferred_called(self):
        w = DeferWaiter()
        w.add(defer.succeed(None))
        d = w.wait()
        self.assertTrue(d.called)

    def test_add_non_deferred(self):
        w = DeferWaiter()
        w.add(2)
        d = w.wait()
        self.assertTrue(d.called)

    def test_add_deferred_not_called_and_call_later(self):
        w = DeferWaiter()

        d1 = defer.Deferred()
        w.add(d1)

        d = w.wait()
        self.assertFalse(d.called)

        d1.callback(None)
        self.assertTrue(d.called)
