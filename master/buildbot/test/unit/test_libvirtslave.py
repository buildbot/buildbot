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

import mock
from twisted.trial import unittest
from twisted.internet import defer, reactor
from buildbot import libvirtbuildslave, config
from buildbot.test.fake import fakemaster

class TestLibVirtSlave(unittest.TestCase):

    class ConcreteBuildSlave(libvirtbuildslave.LibVirtSlave):
        pass

    def test_constructor_nolibvirt(self):
        self.patch(libvirtbuildslave, "libvirt", None)
        self.assertRaises(config.ConfigErrors, self.ConcreteBuildSlave,
            'bot', 'pass', None, 'path', 'path')

    def test_constructor_minimal(self):
        self.patch(libvirtbuildslave, "libvirt", mock.Mock())

        connection = mock.Mock()
        connection.all.return_value = []

        bs = self.ConcreteBuildSlave('bot', 'pass', connection, 'path', 'otherpath')
        self.assertEqual(bs.slavename, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.connection, connection)
        self.assertEqual(bs.image, 'path')
        self.assertEqual(bs.base_image, 'otherpath')
        self.assertEqual(bs.keepalive_interval, 3600)


class TestWorkQueue(unittest.TestCase):

    def setUp(self):
        self.queue = libvirtbuildslave.WorkQueue()

    def delayed_success(self):
        def work():
            d = defer.Deferred()
            reactor.callLater(0, d.callback, True)
            return d
        return work

    def delayed_errback(self):
        def work():
            d = defer.Deferred()
            reactor.callLater(0, d.errback, Failure("Test failure"))
            return d
        return work

    def expect_errback(self, d):
        def shouldnt_get_called(f):
            self.failUnlessEqual(True, False)
        d.addCallback(shouldnt_get_called)
        def errback(f):
            #log.msg("errback called?")
            pass
        d.addErrback(errback)
        return d

    def test_handle_exceptions(self):
        def work():
            raise ValueError
        return self.expect_errback(self.queue.execute(work))

    def test_handle_immediate_errback(self):
        def work():
            return defer.fail("Sad times")
        return self.expect_errback(self.queue.execute(work))

    def test_handle_delayed_errback(self):
        work = self.delayed_errback()
        return self.expect_errback(self.queue.execute(work))

    def test_handle_immediate_success(self):
        def work():
            return defer.succeed(True)
        return self.queue.execute(work)

    def test_handle_delayed_success(self):
        work = self.delayed_success()
        return self.queue.execute(work)

    def test_single_pow_fires(self):
        return self.queue.execute(self.delayed_success())

    def test_single_pow_errors_gracefully(self):
        d = self.queue.execute(self.delayed_errback())
        return self.expect_errback(d)

    def test_fail_doesnt_break_further_work(self):
        self.expect_errback(self.queue.execute(self.delayed_errback()))
        return self.queue.execute(self.delayed_success())

    def test_second_pow_fires(self):
        self.queue.execute(self.delayed_success())
        return self.queue.execute(self.delayed_success())

    def test_work(self):
        # We want these deferreds to fire in order
        flags = {1: False, 2: False, 3: False }

        # When first deferred fires, flags[2] and flags[3] should still be false
        # flags[1] shouldnt already be set, either
        d1 = self.queue.execute(self.delayed_success())
        def cb1(res):
            self.failUnlessEqual(flags[1], False)
            flags[1] = True
            self.failUnlessEqual(flags[2], False)
            self.failUnlessEqual(flags[3], False)
        d1.addCallback(cb1)

        # When second deferred fires, only flags[3] should be set
        # flags[2] should definitely be False
        d2 = self.queue.execute(self.delayed_success())
        def cb2(res):
            assert flags[2] == False
            flags[2] = True
            assert flags[1] == True
            assert flags[3] == False
        d2.addCallback(cb2)

        # When third deferred fires, only flags[3] should be unset
        d3 = self.queue.execute(self.delayed_success())
        def cb3(res):
            assert flags[3] == False
            flags[3] = True
            assert flags[1] == True
            assert flags[2] == True
        d3.addCallback(cb3)

        return defer.DeferredList([d1, d2, d3], fireOnOneErrback=True)

