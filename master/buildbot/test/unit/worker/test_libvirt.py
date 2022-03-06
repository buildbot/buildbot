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

import socket

from parameterized import parameterized

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.test.fake import libvirt as libvirtfake
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.runprocess import ExpectMasterShell
from buildbot.test.runprocess import MasterRunProcessMixin
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.warnings import DeprecatedApiWarning
from buildbot.worker import libvirt as libvirtworker


# The libvirt module has a singleton threadpool within the module which we can't use in tests as
# this makes it impossible to run them concurrently. To work around this we introduce a per-test
# threadpool and access it through a class instance
class TestThreadWithQueue(libvirtworker.ThreadWithQueue):
    def __init__(self, pool, uri):
        super().__init__(pool, uri, connect_backoff_start_seconds=0, connect_backoff_multiplier=0,
                         connect_backoff_max_wait_seconds=0)

    def libvirt_open(self):
        return self.pool.case.libvirt_open(self.uri)


class TestServerThreadPool(libvirtworker.ServerThreadPool):
    ThreadClass = TestThreadWithQueue

    def __init__(self, case):
        super().__init__()
        self.case = case


class TestLibvirtWorker(libvirtworker.LibVirtWorker):
    def __init__(self, case, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.case = case
        self.pool = case.threadpool


class TestException(Exception):
    pass


class TestLibVirtWorker(TestReactorMixin, MasterRunProcessMixin, unittest.TestCase):
    def setUp(self):
        self.setup_test_reactor()
        self.setup_master_run_process()
        self.connections = {}
        self.patch(libvirtworker, "libvirt", libvirtfake)
        self.threadpool = TestServerThreadPool(self)

    def libvirt_open(self, uri):
        if uri not in self.connections:
            raise Exception('Could not find test connection')
        return self.connections[uri]

    def add_fake_conn(self, uri):
        conn = libvirtfake.Connection(uri)
        self.connections[uri] = conn
        return conn

    def create_worker(self, *args, **kwargs):
        worker = TestLibvirtWorker(self, *args, **kwargs)
        worker.parent = mock.Mock()
        worker.parent.master = mock.Mock()
        worker.parent.master.reactor = self.reactor
        return worker

    def raise_libvirt_error(self):
        # Helper method to be used from lambdas as they don't accept statements
        raise libvirtfake.libvirtError()

    def test_constructor_nolibvirt(self):
        self.patch(libvirtworker, "libvirt", None)
        with self.assertRaises(config.ConfigErrors):
            self.create_worker('bot', 'pass', None, 'path', 'path')

    def test_deprecated_connection(self):
        with assertProducesWarnings(DeprecatedApiWarning,
                                    message_pattern='connection argument has been deprecated'):
            self.create_worker('bot', 'pass', libvirtworker.Connection('test'), 'path', 'path')

    def test_deprecated_connection_and_uri(self):
        with self.assertRaises(config.ConfigErrors):
            with assertProducesWarnings(DeprecatedApiWarning,
                                        message_pattern='connection argument has been deprecated'):
                self.create_worker('bot', 'pass', libvirtworker.Connection('test'), 'path', 'path',
                                   uri='custom')

    @defer.inlineCallbacks
    def test_get_domain_id(self):
        conn = self.add_fake_conn('fake:///conn')
        conn.fake_add('bot', 14)

        bs = self.create_worker('bot', 'pass', hd_image='p', base_image='o', uri='fake:///conn')

        id = yield bs._get_domain_id()
        self.assertEqual(id, 14)

    @defer.inlineCallbacks
    def test_prepare_base_image_none(self):
        bs = self.create_worker('bot', 'pass', hd_image='p', base_image=None)
        yield bs._prepare_base_image()

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_prepare_base_image_cheap(self):
        self.expect_commands(
            ExpectMasterShell(["qemu-img", "create", "-b", "o", "-f", "qcow2", "p"])
        )

        bs = self.create_worker('bot', 'pass', hd_image='p', base_image='o')
        yield bs._prepare_base_image()

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_prepare_base_image_full(self):
        self.expect_commands(
            ExpectMasterShell(["cp", "o", "p"])
        )

        bs = self.create_worker('bot', 'pass', hd_image='p', base_image='o')
        bs.cheap_copy = False
        yield bs._prepare_base_image()

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_prepare_base_image_fail(self):
        self.expect_commands(
            ExpectMasterShell(["cp", "o", "p"])
            .exit(1)
        )

        bs = self.create_worker('bot', 'pass', hd_image='p', base_image='o')
        bs.cheap_copy = False
        with self.assertRaises(LatentWorkerFailedToSubstantiate):
            yield bs._prepare_base_image()

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def _test_stop_instance(self, graceful, fast, expected_destroy,
                            expected_shutdown, shutdown_side_effect=None):
        domain = mock.Mock()
        domain.ID.side_effect = lambda: 14
        domain.shutdown.side_effect = shutdown_side_effect

        conn = self.add_fake_conn('fake:///conn')
        conn.fake_add_domain('name', domain)

        bs = self.create_worker('name', 'p', hd_image='p', base_image='o',
                                uri='fake:///conn', xml='<xml/>')
        bs.graceful_shutdown = graceful
        with mock.patch('os.remove') as remove_mock:
            yield bs.stop_instance(fast=fast)

        self.assertEqual(int(expected_destroy), domain.destroy.call_count)
        self.assertEqual(int(expected_shutdown), domain.shutdown.call_count)
        remove_mock.assert_called_once_with('p')

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_stop_instance_destroy(self):
        yield self._test_stop_instance(graceful=False,
                                       fast=False,
                                       expected_destroy=True,
                                       expected_shutdown=False)

    @defer.inlineCallbacks
    def test_stop_instance_shutdown(self):
        yield self._test_stop_instance(graceful=True,
                                       fast=False,
                                       expected_destroy=False,
                                       expected_shutdown=True)

    @defer.inlineCallbacks
    def test_stop_instance_shutdown_fails(self):
        yield self._test_stop_instance(graceful=True,
                                       fast=False,
                                       expected_destroy=True,
                                       expected_shutdown=True,
                                       shutdown_side_effect=TestException)

    @defer.inlineCallbacks
    def test_start_instance_connection_fails(self):
        bs = self.create_worker('b', 'p', hd_image='p', base_image='o', uri='unknown')

        prep = mock.Mock()
        prep.side_effect = lambda: defer.succeed(0)
        self.patch(bs, "_prepare_base_image", prep)

        with self.assertRaisesRegex(LatentWorkerFailedToSubstantiate, 'Did not receive connection'):
            yield bs.start_instance(mock.Mock())

        self.assertFalse(prep.called)

    @defer.inlineCallbacks
    def test_start_instance_already_active(self):
        conn = self.add_fake_conn('fake:///conn')
        conn.fake_add('bot', 14)

        bs = self.create_worker('bot', 'p', hd_image='p', base_image='o', uri='fake:///conn',
                                xml='<xml/>')

        prep = mock.Mock()
        self.patch(bs, "_prepare_base_image", prep)

        with self.assertRaisesRegex(LatentWorkerFailedToSubstantiate, 'it\'s already active'):
            yield bs.start_instance(mock.Mock())

        self.assertFalse(prep.called)

    @defer.inlineCallbacks
    def test_start_instance_domain_id_error(self):
        conn = self.add_fake_conn('fake:///conn')
        domain = conn.fake_add('bot', 14)
        domain.ID = self.raise_libvirt_error

        bs = self.create_worker('bot', 'p', hd_image='p', base_image='o', uri='fake:///conn',
                                xml='<xml/>')

        prep = mock.Mock()
        self.patch(bs, "_prepare_base_image", prep)

        with self.assertRaisesRegex(LatentWorkerFailedToSubstantiate, 'while retrieving domain ID'):
            yield bs.start_instance(mock.Mock())

        self.assertFalse(prep.called)

    @defer.inlineCallbacks
    def test_start_instance_connection_create_fails(self):
        bs = self.create_worker('bot', 'p', hd_image='p', base_image='o', xml='<xml/>',
                                uri='fake:///conn')

        conn = self.add_fake_conn('fake:///conn')
        conn.createXML = lambda _, __: self.raise_libvirt_error()

        prep = mock.Mock()
        prep.side_effect = lambda: defer.succeed(0)
        self.patch(bs, "_prepare_base_image", prep)

        with self.assertRaisesRegex(LatentWorkerFailedToSubstantiate, 'error while starting VM'):
            yield bs.start_instance(mock.Mock())

        self.assertTrue(prep.called)

    @defer.inlineCallbacks
    def test_start_instance_domain_create_fails(self):
        bs = self.create_worker('bot', 'p', hd_image='p', base_image='o', uri='fake:///conn')

        conn = self.add_fake_conn('fake:///conn')
        domain = conn.fake_add('bot', -1)
        domain.create = self.raise_libvirt_error

        prep = mock.Mock()
        prep.side_effect = lambda: defer.succeed(0)
        self.patch(bs, "_prepare_base_image", prep)

        with self.assertRaisesRegex(LatentWorkerFailedToSubstantiate, 'error while starting VM'):
            yield bs.start_instance(mock.Mock())

        self.assertTrue(prep.called)

    @defer.inlineCallbacks
    def test_start_instance_xml(self):
        self.add_fake_conn('fake:///conn')

        bs = self.create_worker('bot', 'p', hd_image='p', base_image='o', uri='fake:///conn',
                                xml='<xml/>')

        prep = mock.Mock()
        prep.side_effect = lambda: defer.succeed(0)
        self.patch(bs, "_prepare_base_image", prep)

        started = yield bs.start_instance(mock.Mock())

        self.assertEqual(started, True)

    @parameterized.expand([
        ('set_fqdn', {'masterFQDN': 'somefqdn'}, 'somefqdn'),
        ('auto_fqdn', {}, socket.getfqdn()),
    ])
    @defer.inlineCallbacks
    def test_start_instance_existing_domain(self, name, kwargs, expect_fqdn):
        conn = self.add_fake_conn('fake:///conn')
        domain = conn.fake_add('bot', -1)

        bs = self.create_worker('bot', 'p', hd_image='p', base_image='o', uri='fake:///conn',
                                **kwargs)

        prep = mock.Mock()
        prep.side_effect = lambda: defer.succeed(0)
        self.patch(bs, "_prepare_base_image", prep)

        started = yield bs.start_instance(mock.Mock())

        self.assertEqual(started, True)
        self.assertEqual(domain.metadata, {
            'buildbot': (libvirtfake.VIR_DOMAIN_METADATA_ELEMENT,
                         'http://buildbot.net/',
                         f'<auth username="bot" password="p" master="{expect_fqdn}"/>',
                         libvirtfake.VIR_DOMAIN_AFFECT_CONFIG)
        })
