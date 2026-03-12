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

from __future__ import annotations

import socket
from typing import TYPE_CHECKING
from typing import Any
from unittest import mock

from parameterized import parameterized
from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.test.fake import libvirt as libvirtfake
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.runprocess import ExpectMasterShell
from buildbot.test.runprocess import MasterRunProcessMixin
from buildbot.worker import libvirt as libvirtworker

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


# The libvirt module has a singleton threadpool within the module which we can't use in tests as
# this makes it impossible to run them concurrently. To work around this we introduce a per-test
# threadpool and access it through a class instance
class TestThreadWithQueue(libvirtworker.ThreadWithQueue):
    def __init__(self, pool: TestServerThreadPool, uri: str) -> None:
        super().__init__(
            pool,
            uri,
            connect_backoff_start_seconds=0,
            connect_backoff_multiplier=0,
            connect_backoff_max_wait_seconds=0,
        )

    def libvirt_open(self) -> libvirtfake.Connection:
        return self.pool.case.libvirt_open(self.uri)


class TestServerThreadPool(libvirtworker.ServerThreadPool):
    ThreadClass = TestThreadWithQueue

    def __init__(self, case: TestLibVirtWorker) -> None:
        super().__init__()
        self.case = case


class TestLibvirtWorker(libvirtworker.LibVirtWorker):
    def __init__(self, case: TestLibVirtWorker, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.case = case
        self.pool = case.threadpool


class TestException(Exception):
    pass


class TestLibVirtWorker(TestReactorMixin, MasterRunProcessMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.setup_test_reactor()
        self.setup_master_run_process()
        self.connections: dict[str, libvirtfake.Connection] = {}
        self.patch(libvirtworker, "libvirt", libvirtfake)
        self.threadpool = TestServerThreadPool(self)

    def libvirt_open(self, uri: str) -> libvirtfake.Connection:
        if uri not in self.connections:
            raise RuntimeError('Could not find test connection')
        return self.connections[uri]

    def add_fake_conn(self, uri: str) -> libvirtfake.Connection:
        conn = libvirtfake.Connection(uri)
        self.connections[uri] = conn
        return conn

    def create_worker(self, *args: Any, **kwargs: Any) -> TestLibvirtWorker:
        worker = TestLibvirtWorker(self, *args, **kwargs)
        worker.parent = mock.Mock()  # type: ignore[assignment]
        worker.parent.master = mock.Mock()  # type: ignore[attr-defined]
        worker.parent.master.reactor = self.reactor  # type: ignore[attr-defined]
        return worker

    def raise_libvirt_error(self) -> None:
        # Helper method to be used from lambdas as they don't accept statements
        raise libvirtfake.libvirtError()

    def test_constructor_nolibvirt(self) -> None:
        self.patch(libvirtworker, "libvirt", None)
        with self.assertRaises(config.ConfigErrors):
            self.create_worker('bot', 'pass', None, 'path', 'path')

    @defer.inlineCallbacks
    def test_get_domain_id(self) -> InlineCallbacksType[None]:
        conn = self.add_fake_conn('fake:///conn')
        conn.fake_add('bot', 14)

        bs = self.create_worker('bot', 'pass', hd_image='p', base_image='o', uri='fake:///conn')

        id = yield bs._get_domain_id()
        self.assertEqual(id, 14)

    @defer.inlineCallbacks
    def test_prepare_base_image_none(self) -> InlineCallbacksType[None]:
        bs = self.create_worker('bot', 'pass', hd_image='p', base_image=None)
        yield bs._prepare_base_image()

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_prepare_base_image_cheap(self) -> InlineCallbacksType[None]:
        self.expect_commands(
            ExpectMasterShell([
                "qemu-img",
                "create",
                "-o",
                "backing_fmt=qcow2",
                "-b",
                "o",
                "-f",
                "qcow2",
                "p",
            ])
        )

        bs = self.create_worker('bot', 'pass', hd_image='p', base_image='o')
        yield bs._prepare_base_image()

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_prepare_base_image_full(self) -> InlineCallbacksType[None]:
        self.expect_commands(ExpectMasterShell(["cp", "o", "p"]))

        bs = self.create_worker('bot', 'pass', hd_image='p', base_image='o')
        bs.cheap_copy = False
        yield bs._prepare_base_image()

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_prepare_base_image_fail(self) -> InlineCallbacksType[None]:
        self.expect_commands(ExpectMasterShell(["cp", "o", "p"]).exit(1))

        bs = self.create_worker('bot', 'pass', hd_image='p', base_image='o')
        bs.cheap_copy = False
        with self.assertRaises(LatentWorkerFailedToSubstantiate):
            yield bs._prepare_base_image()

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def _test_stop_instance(
        self,
        graceful: bool,
        fast: bool,
        expected_destroy: bool,
        expected_shutdown: bool,
        shutdown_side_effect: type[Exception] | None = None,
    ) -> InlineCallbacksType[None]:
        domain = mock.Mock()
        domain.ID.side_effect = lambda: 14
        domain.shutdown.side_effect = shutdown_side_effect

        conn = self.add_fake_conn('fake:///conn')
        conn.fake_add_domain('name', domain)

        bs = self.create_worker(
            'name', 'p', hd_image='p', base_image='o', uri='fake:///conn', xml='<xml/>'
        )
        bs.graceful_shutdown = graceful
        with mock.patch('os.remove') as remove_mock:
            yield bs.stop_instance(fast=fast)

        self.assertEqual(int(expected_destroy), domain.destroy.call_count)
        self.assertEqual(int(expected_shutdown), domain.shutdown.call_count)
        remove_mock.assert_called_once_with('p')

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_stop_instance_destroy(self) -> InlineCallbacksType[None]:
        yield self._test_stop_instance(
            graceful=False, fast=False, expected_destroy=True, expected_shutdown=False
        )

    @defer.inlineCallbacks
    def test_stop_instance_shutdown(self) -> InlineCallbacksType[None]:
        yield self._test_stop_instance(
            graceful=True, fast=False, expected_destroy=False, expected_shutdown=True
        )

    @defer.inlineCallbacks
    def test_stop_instance_shutdown_fails(self) -> InlineCallbacksType[None]:
        yield self._test_stop_instance(
            graceful=True,
            fast=False,
            expected_destroy=True,
            expected_shutdown=True,
            shutdown_side_effect=TestException,
        )

    @defer.inlineCallbacks
    def test_start_instance_connection_fails(self) -> InlineCallbacksType[None]:
        bs = self.create_worker('b', 'p', hd_image='p', base_image='o', uri='unknown')

        prep = mock.Mock()
        prep.side_effect = lambda: defer.succeed(0)
        self.patch(bs, "_prepare_base_image", prep)

        with self.assertRaisesRegex(LatentWorkerFailedToSubstantiate, 'Did not receive connection'):
            yield bs.start_instance(mock.Mock())

        self.assertFalse(prep.called)

    @defer.inlineCallbacks
    def test_start_instance_already_active(self) -> InlineCallbacksType[None]:
        conn = self.add_fake_conn('fake:///conn')
        conn.fake_add('bot', 14)

        bs = self.create_worker(
            'bot', 'p', hd_image='p', base_image='o', uri='fake:///conn', xml='<xml/>'
        )

        prep = mock.Mock()
        self.patch(bs, "_prepare_base_image", prep)

        with self.assertRaisesRegex(LatentWorkerFailedToSubstantiate, 'it\'s already active'):
            yield bs.start_instance(mock.Mock())

        self.assertFalse(prep.called)

    @defer.inlineCallbacks
    def test_start_instance_domain_id_error(self) -> InlineCallbacksType[None]:
        conn = self.add_fake_conn('fake:///conn')
        domain = conn.fake_add('bot', 14)
        domain.ID = self.raise_libvirt_error  # type: ignore[assignment]

        bs = self.create_worker(
            'bot', 'p', hd_image='p', base_image='o', uri='fake:///conn', xml='<xml/>'
        )

        prep = mock.Mock()
        self.patch(bs, "_prepare_base_image", prep)

        with self.assertRaisesRegex(LatentWorkerFailedToSubstantiate, 'while retrieving domain ID'):
            yield bs.start_instance(mock.Mock())

        self.assertFalse(prep.called)

    @defer.inlineCallbacks
    def test_start_instance_connection_create_fails(self) -> InlineCallbacksType[None]:
        bs = self.create_worker(
            'bot', 'p', hd_image='p', base_image='o', xml='<xml/>', uri='fake:///conn'
        )

        conn = self.add_fake_conn('fake:///conn')
        conn.createXML = lambda _, __: self.raise_libvirt_error()  # type: ignore[assignment,return-value]

        prep = mock.Mock()
        prep.side_effect = lambda: defer.succeed(0)
        self.patch(bs, "_prepare_base_image", prep)

        with self.assertRaisesRegex(LatentWorkerFailedToSubstantiate, 'error while starting VM'):
            yield bs.start_instance(mock.Mock())

        self.assertTrue(prep.called)

    @defer.inlineCallbacks
    def test_start_instance_domain_create_fails(self) -> InlineCallbacksType[None]:
        bs = self.create_worker('bot', 'p', hd_image='p', base_image='o', uri='fake:///conn')

        conn = self.add_fake_conn('fake:///conn')
        domain = conn.fake_add('bot', -1)
        domain.create = self.raise_libvirt_error  # type: ignore[method-assign]

        prep = mock.Mock()
        prep.side_effect = lambda: defer.succeed(0)
        self.patch(bs, "_prepare_base_image", prep)

        with self.assertRaisesRegex(LatentWorkerFailedToSubstantiate, 'error while starting VM'):
            yield bs.start_instance(mock.Mock())

        self.assertTrue(prep.called)

    @defer.inlineCallbacks
    def test_start_instance_xml(self) -> InlineCallbacksType[None]:
        self.add_fake_conn('fake:///conn')

        bs = self.create_worker(
            'bot', 'p', hd_image='p', base_image='o', uri='fake:///conn', xml='<xml/>'
        )

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
    def test_start_instance_existing_domain(
        self, name: str, kwargs: dict[str, Any], expect_fqdn: str
    ) -> InlineCallbacksType[None]:
        conn = self.add_fake_conn('fake:///conn')
        domain = conn.fake_add('bot', -1)

        bs = self.create_worker(
            'bot', 'p', hd_image='p', base_image='o', uri='fake:///conn', **kwargs
        )

        prep = mock.Mock()
        prep.side_effect = lambda: defer.succeed(0)
        self.patch(bs, "_prepare_base_image", prep)

        started = yield bs.start_instance(mock.Mock())

        self.assertEqual(started, True)
        self.assertEqual(
            domain.metadata,
            {
                'buildbot': (
                    libvirtfake.VIR_DOMAIN_METADATA_ELEMENT,
                    'http://buildbot.net/',
                    f'<auth username="bot" password="p" master="{expect_fqdn}"/>',
                    libvirtfake.VIR_DOMAIN_AFFECT_CONFIG,
                )
            },
        )
