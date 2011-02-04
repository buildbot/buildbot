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
from twisted.internet import defer, reactor
from buildbot.test.util import changesource
from buildbot.changes import base

class TestPollingChangeSource(changesource.ChangeSourceMixin, unittest.TestCase):
    class Subclass(base.PollingChangeSource):
        polledFn = None
        shouldFail = False

        def poll(self):
            reactor.callLater(0, self.polledFn)
            if self.shouldFail:
                return defer.fail(RuntimeError("your failure, sir"))
            return defer.succeed(None)

    def setUp(self):
        d = self.setUpChangeSource()
        def create_changesource(_):
            self.attachChangeSource(self.Subclass())
        d.addCallback(create_changesource)
        return d

    def tearDown(self):
        return self.tearDownChangeSource()

    def test_loop_loops(self):
        d = defer.Deferred()
        self.changesource.polledFn = lambda : d.callback(None)
        self.startChangeSource()
        return d
