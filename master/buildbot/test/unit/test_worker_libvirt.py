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

from twisted.internet import defer
from twisted.internet import utils
from twisted.python import failure
from twisted.trial import unittest

from buildbot import config
from buildbot.test.fake import libvirt
from buildbot.test.util.misc import TestReactorMixin
from buildbot.util import eventual
from buildbot.worker import libvirt as libvirtworker


class TestLibVirtWorker(unittest.TestCase):

    class ConcreteWorker(libvirtworker.LibVirtWorker):
        pass

    def setUp(self):
        self.patch(libvirtworker, "libvirt", libvirt)
        self.conn = libvirtworker.Connection("test://")
        self.lvconn = self.conn.connection

    def test_constructor_nolibvirt(self):
        self.patch(libvirtworker, "libvirt", None)
        with self.assertRaises(config.ConfigErrors):
            self.ConcreteWorker('bot', 'pass', None, 'path', 'path')

    @defer.inlineCallbacks
    def test_constructor_minimal(self):
        bs = self.ConcreteWorker('bot', 'pass', self.conn, 'path', 'otherpath')
        yield bs._find_existing_deferred
        self.assertEqual(bs.workername, 'bot')
        self.assertEqual(bs.password, 'pass')
        self.assertEqual(bs.connection, self.conn)
        self.assertEqual(bs.image, 'path')
        self.assertEqual(bs.base_image, 'otherpath')

    @defer.inlineCallbacks
    def test_find_existing(self):
        d = self.lvconn.fake_add("bot")

        bs = self.ConcreteWorker('bot', 'pass', self.conn, 'p', 'o')
        yield bs._find_existing_deferred

        self.assertEqual(bs.domain.domain, d)

    @defer.inlineCallbacks
    def test_prepare_base_image_none(self):
        self.patch(utils, "getProcessValue", mock.Mock())
        utils.getProcessValue.side_effect = lambda x, y: defer.succeed(0)

        bs = self.ConcreteWorker('bot', 'pass', self.conn, 'p', None)
        yield bs._find_existing_deferred
        yield bs._prepare_base_image()

        self.assertEqual(utils.getProcessValue.call_count, 0)

    @defer.inlineCallbacks
    def test_prepare_base_image_cheap(self):
        self.patch(utils, "getProcessValue", mock.Mock())
        utils.getProcessValue.side_effect = lambda x, y: defer.succeed(0)

        bs = self.ConcreteWorker('bot', 'pass', self.conn, 'p', 'o')
        yield bs._find_existing_deferred
        yield bs._prepare_base_image()

        utils.getProcessValue.assert_called_with(
            "qemu-img", ["create", "-b", "o", "-f", "qcow2", "p"])

    @defer.inlineCallbacks
    def test_prepare_base_image_full(self):
        self.patch(utils, "getProcessValue", mock.Mock())
        utils.getProcessValue.side_effect = lambda x, y: defer.succeed(0)

        bs = self.ConcreteWorker('bot', 'pass', self.conn, 'p', 'o')
        yield bs._find_existing_deferred
        bs.cheap_copy = False
        yield bs._prepare_base_image()

        utils.getProcessValue.assert_called_with(
            "cp", ["o", "p"])

    @defer.inlineCallbacks
    def test_start_instance(self):
        bs = self.ConcreteWorker('b', 'p', self.conn, 'p', 'o',
                                 xml='<xml/>')

        prep = mock.Mock()
        prep.side_effect = lambda: defer.succeed(0)
        self.patch(bs, "_prepare_base_image", prep)

        yield bs._find_existing_deferred
        started = yield bs.start_instance(mock.Mock())

        self.assertEqual(started, True)

    @defer.inlineCallbacks
    def test_start_instance_create_fails(self):
        bs = self.ConcreteWorker('b', 'p', self.conn, 'p', 'o',
                                 xml='<xml/>')

        prep = mock.Mock()
        prep.side_effect = lambda: defer.succeed(0)
        self.patch(bs, "_prepare_base_image", prep)

        create = mock.Mock()
        create.side_effect = lambda self: defer.fail(
            failure.Failure(RuntimeError('oh noes')))
        self.patch(libvirtworker.Connection, 'create', create)

        yield bs._find_existing_deferred
        started = yield bs.start_instance(mock.Mock())

        self.assertEqual(bs.domain, None)
        self.assertEqual(started, False)
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    @defer.inlineCallbacks
    def setup_canStartBuild(self):
        bs = self.ConcreteWorker('b', 'p', self.conn, 'p', 'o')
        yield bs._find_existing_deferred
        bs.updateLocks()
        return bs

    @defer.inlineCallbacks
    def test_canStartBuild(self):
        bs = yield self.setup_canStartBuild()
        self.assertEqual(bs.canStartBuild(), True)

    @defer.inlineCallbacks
    def test_canStartBuild_notready(self):
        """
        If a LibVirtWorker hasn't finished scanning for existing VMs then we shouldn't
        start builds on it as it might create a 2nd VM when we want to reuse the existing
        one.
        """
        bs = yield self.setup_canStartBuild()
        bs.ready = False
        self.assertEqual(bs.canStartBuild(), False)

    @defer.inlineCallbacks
    def test_canStartBuild_domain_and_not_connected(self):
        """
        If we've found that the VM this worker would instance already exists but hasn't
        connected then we shouldn't start builds or we'll end up with a dupe.
        """
        bs = yield self.setup_canStartBuild()
        bs.domain = mock.Mock()
        self.assertEqual(bs.canStartBuild(), False)

    @defer.inlineCallbacks
    def test_canStartBuild_domain_and_connected(self):
        """
        If we've found an existing VM and it is connected then we should start builds
        """
        bs = yield self.setup_canStartBuild()
        bs.domain = mock.Mock()
        isconnected = mock.Mock()
        isconnected.return_value = True
        self.patch(bs, "isConnected", isconnected)
        self.assertEqual(bs.canStartBuild(), True)


class TestWorkQueue(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()

    def tearDown(self):
        return eventual.flushEventualQueue()

    def delayed_success(self):
        def work():
            d = defer.Deferred()
            self.reactor.callLater(0, d.callback, True)
            return d
        return work

    def delayed_errback(self):
        def work():
            d = defer.Deferred()
            self.reactor.callLater(0, d.errback,
                                   failure.Failure(
                                       RuntimeError("Test failure")))
            return d
        return work

    def expect_errback(self, d):
        @d.addCallback
        def shouldnt_get_called(f):
            self.assertEqual(True, False)

        @d.addErrback
        def errback(f):
            """ log.msg("errback called?") """

        return d

    @defer.inlineCallbacks
    def test_handle_exceptions(self):
        queue = libvirtworker.WorkQueue()

        def work():
            raise ValueError
        yield self.expect_errback(queue.execute(work))

    @defer.inlineCallbacks
    def test_handle_immediate_errback(self):
        queue = libvirtworker.WorkQueue()

        def work():
            return defer.fail(RuntimeError("Sad times"))
        yield self.expect_errback(queue.execute(work))

    @defer.inlineCallbacks
    def test_handle_delayed_errback(self):
        queue = libvirtworker.WorkQueue()
        work = self.delayed_errback()
        yield self.expect_errback(queue.execute(work))

    @defer.inlineCallbacks
    def test_handle_immediate_success(self):
        queue = libvirtworker.WorkQueue()

        def work():
            return defer.succeed(True)
        yield queue.execute(work)

    @defer.inlineCallbacks
    def test_handle_delayed_success(self):
        queue = libvirtworker.WorkQueue()
        work = self.delayed_success()
        yield queue.execute(work)

    @defer.inlineCallbacks
    def test_single_pow_fires(self):
        queue = libvirtworker.WorkQueue()
        yield queue.execute(self.delayed_success())

    @defer.inlineCallbacks
    def test_single_pow_errors_gracefully(self):
        queue = libvirtworker.WorkQueue()
        d = queue.execute(self.delayed_errback())
        yield self.expect_errback(d)

    @defer.inlineCallbacks
    def test_fail_doesnt_break_further_work(self):
        queue = libvirtworker.WorkQueue()
        yield self.expect_errback(queue.execute(self.delayed_errback()))
        yield queue.execute(self.delayed_success())

    @defer.inlineCallbacks
    def test_second_pow_fires(self):
        queue = libvirtworker.WorkQueue()
        yield queue.execute(self.delayed_success())
        yield queue.execute(self.delayed_success())

    @defer.inlineCallbacks
    def test_work(self):
        queue = libvirtworker.WorkQueue()

        # We want these deferreds to fire in order
        flags = {1: False, 2: False, 3: False}

        # When first deferred fires, flags[2] and flags[3] should still be false
        # flags[1] shouldn't already be set, either
        @defer.inlineCallbacks
        def d1():
            yield queue.execute(self.delayed_success())
            self.assertEqual(flags[1], False)
            flags[1] = True
            self.assertEqual(flags[2], False)
            self.assertEqual(flags[3], False)

        # When second deferred fires, only flags[3] should be set
        # flags[2] should definitely be False
        @defer.inlineCallbacks
        def d2():
            yield queue.execute(self.delayed_success())
            self.assertFalse(flags[2])
            flags[2] = True
            self.assertTrue(flags[1])
            self.assertFalse(flags[3])

        # When third deferred fires, only flags[3] should be unset
        @defer.inlineCallbacks
        def d3():
            yield queue.execute(self.delayed_success())

            self.assertFalse(flags[3])
            flags[3] = True
            self.assertTrue(flags[1])
            self.assertTrue(flags[2])

        yield defer.DeferredList([d1(), d2(), d3()], fireOnOneErrback=True)
