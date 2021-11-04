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

from buildbot.interfaces import LatentWorkerSubstantiatiationCancelled
from buildbot.process.properties import Properties
from buildbot.test.fake import fakebuild
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake.fakeprotocol import FakeTrivialConnection as FakeBot
from buildbot.test.reactor import TestReactorMixin
from buildbot.worker.marathon import MarathonLatentWorker


class TestMarathonLatentWorker(unittest.TestCase, TestReactorMixin):
    def setUp(self):
        self.setup_test_reactor()
        self.build = Properties(
            image="busybox:latest", builder="docker_worker")
        self.worker = None

    def tearDown(self):
        if self.worker is not None:
            class FakeResult:
                code = 200
            self._http.delete = lambda _: defer.succeed(FakeResult())
            self.worker.master.stopService()
        self.flushLoggedErrors(LatentWorkerSubstantiatiationCancelled)

    def test_constructor_normal(self):
        worker = MarathonLatentWorker('bot', 'tcp://marathon.local', 'foo',
                                      'bar', 'debian:wheezy')
        # class instantiation configures nothing
        self.assertEqual(worker._http, None)

    @defer.inlineCallbacks
    def makeWorker(self, **kwargs):
        kwargs.setdefault('image', 'debian:wheezy')
        worker = MarathonLatentWorker('bot', 'tcp://marathon.local', **kwargs)
        self.worker = worker
        master = fakemaster.make_master(self, wantData=True)
        self._http = yield fakehttpclientservice.HTTPClientService.getService(
                master, self, 'tcp://marathon.local', auth=kwargs.get('auth'))
        yield worker.setServiceParent(master)
        worker.reactor = self.reactor
        yield master.startService()
        worker.masterhash = "masterhash"
        return worker

    @defer.inlineCallbacks
    def test_builds_may_be_incompatible(self):
        worker = self.worker = yield self.makeWorker()
        # http is lazily created on worker substantiation
        self.assertEqual(worker.builds_may_be_incompatible, True)

    @defer.inlineCallbacks
    def test_start_service(self):
        worker = self.worker = yield self.makeWorker()
        # http is lazily created on worker substantiation
        self.assertNotEqual(worker._http, None)

    @defer.inlineCallbacks
    def test_start_worker(self):
        # http://mesosphere.github.io/marathon/docs/rest-api.html#post-v2-apps
        worker = yield self.makeWorker()
        worker.password = "pass"
        worker.masterFQDN = "master"
        self._http.expect(
            method='delete',
            ep='/v2/apps/buildbot-worker/buildbot-bot-masterhash')
        self._http.expect(
            method='post',
            ep='/v2/apps',
            json={
                'instances': 1,
                'container': {
                    'docker': {
                        'image': 'rendered:debian:wheezy',
                        'network': 'BRIDGE'
                    },
                    'type': 'DOCKER'
                },
                'id': 'buildbot-worker/buildbot-bot-masterhash',
                'env': {
                    'BUILDMASTER': "master",
                    'BUILDMASTER_PORT': '1234',
                    'WORKERNAME': 'bot',
                    'WORKERPASS': "pass"
                }
            },
            code=201,
            content_json={'Id': 'id'})
        d = worker.substantiate(None, fakebuild.FakeBuildForRendering())
        # we simulate a connection
        worker.attached(FakeBot())
        yield d

        self.assertEqual(worker.instance, {'Id': 'id'})
        # teardown makes sure all containers are cleaned up

    @defer.inlineCallbacks
    def test_start_worker_but_no_connection_and_shutdown(self):
        worker = yield self.makeWorker()
        worker.password = "pass"
        worker.masterFQDN = "master"
        self._http.expect(
            method='delete',
            ep='/v2/apps/buildbot-worker/buildbot-bot-masterhash')
        self._http.expect(
            method='post',
            ep='/v2/apps',
            json={
                'instances': 1,
                'container': {
                    'docker': {
                        'image': 'rendered:debian:wheezy',
                        'network': 'BRIDGE'
                    },
                    'type': 'DOCKER'
                },
                'id': 'buildbot-worker/buildbot-bot-masterhash',
                'env': {
                    'BUILDMASTER': "master",
                    'BUILDMASTER_PORT': '1234',
                    'WORKERNAME': 'bot',
                    'WORKERPASS': "pass"
                }
            },
            code=201,
            content_json={'Id': 'id'})

        worker.substantiate(None, fakebuild.FakeBuildForRendering())
        self.assertEqual(worker.instance, {'Id': 'id'})
        # teardown makes sure all containers are cleaned up

    @defer.inlineCallbacks
    def test_start_worker_but_error(self):
        worker = yield self.makeWorker()
        self._http.expect(
            method='delete',
            ep='/v2/apps/buildbot-worker/buildbot-bot-masterhash')
        self._http.expect(
            method='post',
            ep='/v2/apps',
            json={
                'instances': 1,
                'container': {
                    'docker': {
                        'image': 'rendered:debian:wheezy',
                        'network': 'BRIDGE'
                    },
                    'type': 'DOCKER'
                },
                'id': 'buildbot-worker/buildbot-bot-masterhash',
                'env': {
                    'BUILDMASTER': "master",
                    'BUILDMASTER_PORT': '1234',
                    'WORKERNAME': 'bot',
                    'WORKERPASS': "pass"
                }
            },
            code=404,
            content_json={'message': 'image not found'})
        self._http.expect(
            method='delete',
            ep='/v2/apps/buildbot-worker/buildbot-bot-masterhash')
        d = worker.substantiate(None, fakebuild.FakeBuildForRendering())
        self.reactor.advance(.1)
        with self.assertRaises(Exception):
            yield d
        self.assertEqual(worker.instance, None)
        # teardown makes sure all containers are cleaned up

    @defer.inlineCallbacks
    def test_start_worker_with_params(self):
        # http://mesosphere.github.io/marathon/docs/rest-api.html#post-v2-apps
        worker = yield self.makeWorker(marathon_extra_config={
            'container': {
                'docker': {
                    'network': None
                }
            },
            'env': {
                'PARAMETER': 'foo'
            }
        })
        worker.password = "pass"
        worker.masterFQDN = "master"
        self._http.expect(
            method='delete',
            ep='/v2/apps/buildbot-worker/buildbot-bot-masterhash')
        self._http.expect(
            method='post',
            ep='/v2/apps',
            json={
                'instances': 1,
                'container': {
                    'docker': {
                        'image': 'rendered:debian:wheezy',
                        'network': None
                    },
                    'type': 'DOCKER'
                },
                'id': 'buildbot-worker/buildbot-bot-masterhash',
                'env': {
                    'BUILDMASTER': "master",
                    'BUILDMASTER_PORT': '1234',
                    'WORKERNAME': 'bot',
                    'WORKERPASS': "pass",
                    'PARAMETER': 'foo'
                }
            },
            code=201,
            content_json={'Id': 'id'})
        d = worker.substantiate(None, fakebuild.FakeBuildForRendering())
        # we simulate a connection
        worker.attached(FakeBot())
        yield d

        self.assertEqual(worker.instance, {'Id': 'id'})
        # teardown makes sure all containers are cleaned up
