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
from twisted.python import log
from buildbot.test.util import changesource
from buildbot.changes import base

class TestPollingChangeSource(changesource.ChangeSourceMixin, unittest.TestCase):
    class Subclass(base.PollingChangeSource):
        polledFn = None
        def poll(self):
            reactor.callLater(0, self.polledFn)
            return defer.succeed(None)

    def setUp(self):
        d = self.setUpChangeSource()
        def create_poller(_):
            self.poller = self.Subclass()
        d.addCallback(create_poller)
        return d

    def tearDown(self):
        return self.tearDownChangeSource()

    def test_loop_loops(self):
        test_d = defer.Deferred()
        def polledFn():
            test_d.callback(None)
        self.poller.polledFn = polledFn
        poll_d = self.startChangeSource(self.poller)
        poll_d.addErrback(log.err)
        return defer.DeferredList([ test_d, poll_d ])
