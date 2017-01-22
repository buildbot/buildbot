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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from twisted.python import threadpool
from twisted.trial import unittest

from buildbot import config
from buildbot.process.properties import Properties
from buildbot.test.fake import fakemaster
from buildbot.test.fake import hyper
from buildbot.test.fake.reactor import NonThreadPool
from buildbot.test.fake.reactor import TestReactor
from buildbot.util.eventual import _setReactor
from buildbot.worker import hyper as workerhyper
from buildbot.worker.hyper import HyperLatentWorker


class FakeBuild(object):
    def render(self, r):
        return "rendered:" + r


class FakeBot(object):
    info = {}

    def notifyOnDisconnect(self, n):
        self.n = n

    def remoteSetBuilderList(self, builders):
        return defer.succeed(None)

    def loseConnection(self):
        self.n()


class TestHyperLatentWorker(unittest.SynchronousTestCase):

    def setUp(self):
        self.patch(threadpool, 'ThreadPool', NonThreadPool)
        self.reactor = TestReactor()
        _setReactor(self.reactor)
        self.patch(workerhyper, 'Hyper', hyper.Client)
        self.build = Properties(
            image="busybox:latest", builder="docker_worker")
        self.worker = None

    def tearDown(self):
        if self.worker is not None:
            self.worker.master.stopService()
            self.reactor.pump([.1])
        self.assertIsNone(hyper.Client.instance)
        _setReactor(None)

    def test_constructor_normal(self):
        worker = HyperLatentWorker('bot', 'pass', 'tcp://hyper.sh/', 'foo', 'bar', 'debian:wheezy')
        # class instantiation configures nothing
        self.assertEqual(worker.client, None)

    def test_constructor_nohyper(self):
        self.patch(workerhyper, 'Hyper', None)
        self.assertRaises(config.ConfigErrors, HyperLatentWorker,
                          'bot', 'pass', 'tcp://hyper.sh/', 'foo', 'bar', 'debian:wheezy')

    def test_constructor_badsize(self):
        self.assertRaises(config.ConfigErrors, HyperLatentWorker,
                          'bot', 'pass', 'tcp://hyper.sh/', 'foo', 'bar', 'debian:wheezy', hyper_size="big")

    def makeWorker(self, **kwargs):
        kwargs.setdefault('image', 'debian:wheezy')
        worker = HyperLatentWorker('bot', 'pass', 'tcp://hyper.sh/', 'foo', 'bar', **kwargs)
        self.worker = worker
        master = fakemaster.make_master(testcase=self, wantData=True)
        worker.setServiceParent(master)
        worker.reactor = self.reactor
        self.successResultOf(master.startService())
        return worker

    def test_start_service(self):
        worker = self.worker = self.makeWorker()
        # client is lazily created on worker substantiation
        self.assertNotEqual(worker.client, None)

    def test_start_worker(self):
        worker = self.makeWorker()

        d = worker.substantiate(None, FakeBuild())
        # we simulate a connection
        worker.attached(FakeBot())
        self.successResultOf(d)

        self.assertIsNotNone(worker.client)
        self.assertEqual(worker.instance, {
            'Id': '8a61192da2b3bb2d922875585e29b74ec0dc4e0117fcbf84c962204e97564cd7',
            'Warnings': None,
            'image': 'rendered:debian:wheezy'})
        # teardown makes sure all containers are cleaned up

    def test_start_worker_but_no_connection_and_shutdown(self):
        worker = self.makeWorker()
        worker.substantiate(None, FakeBuild())
        self.assertIsNotNone(worker.client)
        self.assertEqual(worker.instance, {
            'Id': '8a61192da2b3bb2d922875585e29b74ec0dc4e0117fcbf84c962204e97564cd7',
            'Warnings': None,
            'image': 'rendered:debian:wheezy'})
        # teardown makes sure all containers are cleaned up

    def test_start_worker_but_error(self):
        worker = self.makeWorker(image="buggy")
        d = worker.substantiate(None, FakeBuild())
        self.reactor.advance(.1)
        self.failureResultOf(d)
        self.assertIsNotNone(worker.client)
        self.assertEqual(worker.instance, None)
        # teardown makes sure all containers are cleaned up

    def test_start_worker_but_already_created_with_same_name(self):
        worker = self.makeWorker(image="cool")
        worker.client.create_container(image="foo", name=worker.getContainerName())
        d = worker.substantiate(None, FakeBuild())
        self.reactor.advance(.1)
        worker.attached(FakeBot())
        self.successResultOf(d)
        self.assertIsNotNone(worker.client)
