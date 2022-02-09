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

import hashlib

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import util
from buildbot.config import ConfigErrors
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.fake.fakebuild import FakeBuildForRendering as FakeBuild
from buildbot.test.fake.fakeprotocol import FakeTrivialConnection as FakeBot
from buildbot.test.reactor import TestReactorMixin
from buildbot.worker import upcloud

# Please see https://developers.upcloud.com/ for details
upcloudStorageTemplatePayload = {
     'storages': {
         'storage': [
             {
                 'access': 'public',
                 'title': 'rendered:test-image',
                 'uuid': '8b47d21b-b4c3-445d-b75c-5a723ff39681'
             }
        ]
    }
}


upcloudServerCreatePayload = {
        'server': {
            'hostname': 'worker',
            'password': 'supersecret',
            'state': 'maintenance',
            'uuid': '438b5b08-4147-4193-bf64-a5318f51d3bd',
            'title': 'buildbot-worker-87de7e',
            'plan': '1xCPU-1GB'
        }
}


upcloudServerStartedPayload = {
        'server': {
            'hostname': 'worker',
            'password': 'supersecret',
            'state': 'started',
            'uuid': '438b5b08-4147-4193-bf64-a5318f51d3bd',
            'title': 'buildbot-worker-87de7e',
            'plan': '1xCPU-1GB'
        }
}

upcloudServerStoppedPayload = {
        'server': {
            'hostname': 'worker',
            'password': 'supersecret',
            'state': 'stopped',
            'uuid': '438b5b08-4147-4193-bf64-a5318f51d3bd',
            'title': 'buildbot-worker-87de7e',
            'plan': '1xCPU-1GB'
        }
}


class TestUpcloudWorker(TestReactorMixin, unittest.TestCase):
    worker = None

    def setUp(self):
        self.setup_test_reactor()

    @defer.inlineCallbacks
    def setupWorker(self, *args, **kwargs):
        worker = upcloud.UpcloudLatentWorker(
                *args, api_username='test-api-user', api_password='test-api-password', **kwargs)
        master = fakemaster.make_master(self, wantData=True)
        self._http = worker.client = yield fakehttpclientservice.HTTPClientService.getService(
            master, self, upcloud.DEFAULT_BASE_URL, auth=('test-api-user', 'test-api-password'),
            debug=False)
        worker.setServiceParent(master)
        yield master.startService()
        self.masterhash = hashlib.sha1(util.unicode2bytes(master.name)).hexdigest()[:6]
        self.addCleanup(master.stopService)
        self.worker = worker
        return worker

    def test_instantiate(self):
        worker = upcloud.UpcloudLatentWorker('test-worker', image='test-image',
                                             api_username='test-api-user',
                                             api_password='test-api-password')
        self.failUnlessIsInstance(worker, upcloud.UpcloudLatentWorker)

    def test_missing_config(self):
        worker = None
        with self.assertRaises(ConfigErrors):
            worker = upcloud.UpcloudLatentWorker('test-worker')
        with self.assertRaises(ConfigErrors):
            worker = upcloud.UpcloudLatentWorker('test-worker', image='test-image')
        with self.assertRaises(ConfigErrors):
            worker = upcloud.UpcloudLatentWorker('test-worker', image='test-image',
                                                 api_username='test-api-user')
        self.assertTrue(worker is None)

    @defer.inlineCallbacks
    def test_missing_image(self):
        worker = yield self.setupWorker('worker', image='no-such-image')
        self._http.expect(method='get', ep='/storage/template',
                          content_json=upcloudStorageTemplatePayload)
        with self.assertRaises(LatentWorkerFailedToSubstantiate):
            yield worker.substantiate(None, FakeBuild())

    @defer.inlineCallbacks
    def test_start_worker(self):
        worker = yield self.setupWorker('worker', image='test-image')
        # resolve image to storage uuid
        self._http.expect(method='get', ep='/storage/template',
                         content_json=upcloudStorageTemplatePayload)
        # actually start server
        self._http.expect(method='post', ep='/server', params=None, data=None, json={'server':
            {'zone': 'de-fra1', 'title': 'buildbot-worker-87de7e', 'hostname': 'worker',
             'user_data': '',
             'login_user': {'username': 'root', 'ssh_keys': {'ssh_key': []}},
             'password_delivery': 'none',
             'storage_devices': {'storage_device': [
                 {'action': 'clone', 'storage': '8b47d21b-b4c3-445d-b75c-5a723ff39681', 'title':
                  f'buildbot-worker-{self.masterhash}', 'size': 10, 'tier': 'maxiops'}]},
             'plan': '1xCPU-1GB'}},
            content_json=upcloudServerCreatePayload, code=202)
        # determine it's up & running
        self._http.expect(method='get', ep='/server/438b5b08-4147-4193-bf64-a5318f51d3bd',
                          content_json=upcloudServerStartedPayload)
        # get root password
        self._http.expect(method='get', ep='/server/438b5b08-4147-4193-bf64-a5318f51d3bd',
                          content_json=upcloudServerStartedPayload)
        # stop server
        self._http.expect(method='post', ep='/server/438b5b08-4147-4193-bf64-a5318f51d3bd/stop',
                          json={'stop_server': {'stop_type': 'hard', 'timeout': '1'}},
                          content_json=upcloudServerStartedPayload)
        # now it's stopped
        self._http.expect(method='get', ep='/server/438b5b08-4147-4193-bf64-a5318f51d3bd',
                          content_json=upcloudServerStoppedPayload)
        # then delete it
        self._http.expect(method='delete',
                          ep='/server/438b5b08-4147-4193-bf64-a5318f51d3bd?storages=1', code=204)
        d = worker.substantiate(None, FakeBuild())
        yield worker.attached(FakeBot())
        yield d
