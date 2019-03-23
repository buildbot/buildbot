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

from buildbot.test.fake import fakemaster
from buildbot.test.fake.gce import GCERecorder
from buildbot.test.fake.fakebuild import FakeBuildForRendering as FakeBuild
from buildbot.test.util import config
from buildbot.worker import gce


class Worker(gce.GCELatentWorker):
    def getGCEService(self, sa_credentials):
        return GCERecorder(
            ['https://www.googleapis.com/auth/compute'], sa_credentials,
            project=self.project, zone=self.zone, instance=self.instance,
            renderer=self)


class TestGCEWorker(unittest.TestCase, config.ConfigErrorsMixin):
    worker = None

    @defer.inlineCallbacks
    def createWorker(self, *args, project="p", zone="z", instance="i", image='im',
                     sa_credentials={}, password="password",
                     masterFQDN="master:5050", **kwargs):
        master = fakemaster.make_master()
        worker = Worker(*args, project=project, zone=zone,
            instance=instance, image=image, sa_credentials=sa_credentials,
            password=password, masterFQDN=masterFQDN, **kwargs)
        yield worker.setServiceParent(master)
        yield worker.reconfigService(*args, project=project, zone=zone,
            instance=instance, image=image, sa_credentials=sa_credentials,
            password=password, masterFQDN=masterFQDN, **kwargs)
        return worker

    @defer.inlineCallbacks
    def setUp(self):
        self.worker = yield self.createWorker('test')
        self.gce = self.worker._gce

    def tearDown(self):
        self.gce.finalValidation()

    @defer.inlineCallbacks
    def test_checkConfig_errors_if_no_project_is_given(self):
        with self.assertRaisesConfigError("need to provide project, zone and instance name"):
            yield self.createWorker('test', project=None)

    @defer.inlineCallbacks
    def test_checkConfig_errors_if_no_zone_is_given(self):
        with self.assertRaisesConfigError("need to provide project, zone and instance name"):
            yield self.createWorker('test', zone=None)

    @defer.inlineCallbacks
    def test_checkConfig_errors_if_no_instance_is_given(self):
        with self.assertRaisesConfigError("need to provide project, zone and instance name"):
            yield self.createWorker('test', instance=None)

    @defer.inlineCallbacks
    def test_checkConfig_errors_if_no_credentials_are_given(self):
        with self.assertRaisesConfigError("need to provide Service Account credentials"):
            yield self.createWorker('test', sa_credentials=None)

    @defer.inlineCallbacks
    def test_checkConfig_errors_if_no_image_is_given(self):
        with self.assertRaisesConfigError("need to provide a base disk image"):
            yield self.createWorker('test', image=None)

    def test_getMetadataFromState_converts_metadata_to_dict(self):
        (f, d) = self.worker.getMetadataFromState({'metadata': {
            'fingerprint': 'finger',
            'items': [
                {'key': 'k0', 'value': 'v0'},
                {'key': 'k1', 'value': 'v1'}
            ]
       }})
        self.assertEqual("finger", f)
        self.assertEqual({'k0': 'v0', 'k1': 'v1'}, d)

    @defer.inlineCallbacks
    def test_getDesiredMetadata_extracts_port_from_fqdn(self):
        worker = yield self.createWorker('test', masterFQDN="master:5050")
        m = worker.getDesiredMetadata(FakeBuild())
        self.assertEqual({'WORKERNAME': 'test', 'WORKERPASS': 'password',
            'BUILDMASTER': 'master', 'BUILDMASTER_PORT': '5050'}, m)

    @defer.inlineCallbacks
    def test_getDesiredMetadata_uses_default_port_if_unspecified(self):
        worker = yield self.createWorker('test', masterFQDN="master")
        m = worker.getDesiredMetadata(FakeBuild())
        self.assertEqual({'WORKERNAME': 'test', 'WORKERPASS': 'password',
            'BUILDMASTER': 'master', 'BUILDMASTER_PORT': 9989}, m)

    def test_updateMetadata_removes_the_worker_specific_keys(self):
        metadata = {'BUILDBOT_CLEAN': 1}
        result = self.worker.updateMetadata(FakeBuild(), metadata)
        self.assertNotIn('BUILDBOT_CLEAN', result)

    def test_updateMetadata_does_not_modify_the_original(self):
        metadata = {'BUILDBOT_CLEAN': 1}
        self.worker.updateMetadata(FakeBuild(), metadata)
        self.assertIn('BUILDBOT_CLEAN', metadata)

    def test_updateMetadata_merges_the_desired_metadata(self):
        metadata = {'BUILDBOT_CLEAN': 1}
        result = self.worker.updateMetadata(FakeBuild(), metadata)
        self.assertEqual('password', result['WORKERPASS'])

    def test_getCurrentDiskName_returns_the_boot_disk(self):
        disks = [
            {'deviceName': 'd1', 'boot': False},
            {'deviceName': 'd2', 'boot': True}
        ]
        self.assertEqual('d2', self.worker.getCurrentDiskName(disks))

    def test_getCurrentDiskName_returns_null_if_there_is_no_boot_disk(self):
        disks = [
            {'deviceName': 'd1', 'boot': False},
            {'deviceName': 'd2', 'boot': False}
        ]
        self.assertNot(self.worker.getCurrentDiskName(disks))

    def test_getNewDiskName_starts_the_disk_number_at_one(self):
        self.assertEqual("i-1", self.worker.getNewDiskName({}))

    def test_getNewDiskName_uses_disk_gen_plus_one(self):
        result = self.worker.getNewDiskName({'BUILDBOT_DISK_GEN': '2'})
        self.assertEqual("i-3", result)

    def test_getNewDiskName_updates_the_disk_gen_in_the_passed_metadata(self):
        metadata = {'BUILDBOT_DISK_GEN': '2'}
        self.worker.getNewDiskName(metadata)
        self.assertEqual('3', metadata['BUILDBOT_DISK_GEN'])

    def compareMetadata(self, expected, actual):
        actual = actual.copy()
        e_items = sorted(expected['items'], key=lambda i: i['key'])
        a_items = sorted(actual['items'], key=lambda i: i['key'])
        return e_items == a_items and expected['fingerprint'] == actual['fingerprint']

    @defer.inlineCallbacks
    def test_start_instance_nominal_flow(self):
        self.gce.expect('GET', '/compute/v1/projects/p/zones/z/instances/i',
            result={
                'status': 'STOPPED',
                'metadata': {
                    'fingerprint': 'finger',
                    'items': [
                        {'key': 'BUILDBOT_DISK_GEN', 'value': '2'},
                        {'key': 'BUILDBOT_CLEAN', 'value': '1'}
                    ]
               }
           })

        expected_json = {
            'fingerprint': 'finger',
            'items': [
                {'key': 'BUILDBOT_DISK_GEN', 'value': '2'},
                {'key': 'WORKERNAME', 'value': 'test'},
                {'key': 'WORKERPASS', 'value': 'password'},
                {'key': 'BUILDMASTER', 'value': 'master'},
                {'key': 'BUILDMASTER_PORT', 'value': '5050'}
            ],
            'kind': 'compute#metadata'
        }

        setMetadata = self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/setMetadata',
            json=lambda j: self.compareMetadata(expected_json, j))
        self.gce.expectWaitForOperation(setMetadata)
        self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/start')
        self.gce.expectInstanceStateWait('RUNNING')

        result = yield self.worker.start_instance(FakeBuild())
        self.assertTrue(result)

    @defer.inlineCallbacks
    def test_start_instance_stops_the_node_if_it_is_running(self):
        self.gce.expect('GET', '/compute/v1/projects/p/zones/z/instances/i',
            result={
                'status': 'RUNNING',
                'metadata': {
                    'fingerprint': 'finger',
                    'items': [
                        {'key': 'BUILDBOT_DISK_GEN', 'value': '2'},
                        {'key': 'BUILDBOT_CLEAN', 'value': '1'}
                    ]
               }
           })
        self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/stop')

        setMetadata = self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/setMetadata',
            json=GCERecorder.IGNORE)
        self.gce.expectInstanceStateWait('TERMINATED')
        self.gce.expectWaitForOperation(setMetadata)
        self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/start')
        self.gce.expectInstanceStateWait('RUNNING')

        result = yield self.worker.start_instance(FakeBuild())
        self.assertTrue(result)

    @defer.inlineCallbacks
    def test_start_instance_is_not_clean_detaches_and_deletes_the_existing_boot_disk(self):
        self.gce.expect('GET', '/compute/v1/projects/p/zones/z/instances/i',
            result={
                'status': 'TERMINATED',
                'metadata': {
                    'fingerprint': 'finger',
                    'items': [{'key': 'BUILDBOT_DISK_GEN', 'value': '2'}]
               },
                'disks': [{'boot': True, 'deviceName': 'current-boot'}]
           })
        createDisk = self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/disks',
            json={
                'sourceImage': 'projects/p/global/images/im',
                'name': 'i-3',  # BUILDBOT_DISK_GEN + 1
                'type': 'projects/p/zones/z/diskTypes/pd-ssd'
           })
        expected_json = {
            'fingerprint': 'finger',
            'items': [
                {'key': 'BUILDBOT_DISK_GEN', 'value': '3'},
                {'key': 'WORKERNAME', 'value': 'test'},
                {'key': 'WORKERPASS', 'value': 'password'},
                {'key': 'BUILDMASTER', 'value': 'master'},
                {'key': 'BUILDMASTER_PORT', 'value': '5050'}
            ],
            'kind': 'compute#metadata'
        }
        setMetadata = self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/setMetadata',
            json=lambda j: self.compareMetadata(expected_json, j))
        detachDisk = self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/detachDisk',
            params={'deviceName': 'current-boot'})
        self.gce.expectWaitForOperation(detachDisk)
        self.gce.expectOperationRequest(
            'DELETE', '/compute/v1/projects/p/zones/z/disks/current-boot')
        self.gce.expectWaitForOperation(createDisk)
        attachDisk = self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/attachDisk',
            json={
                'boot': True,
                'source': '/compute/v1/projects/p/zones/z/disks/i-3',
                'deviceName': 'i-3',
                'index': 0
           })
        self.gce.expectWaitForOperation(attachDisk)
        self.gce.expectWaitForOperation(setMetadata)
        self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/start')
        self.gce.expectInstanceStateWait('RUNNING')

        result = yield self.worker.start_instance(FakeBuild())
        self.assertTrue(result)

    @defer.inlineCallbacks
    def test_start_instance_is_not_clean_creates_and_attaches_a_boot_disk(self):
        self.gce.expect('GET', '/compute/v1/projects/p/zones/z/instances/i',
            result={
                'status': 'TERMINATED',
                'metadata': {
                    'fingerprint': 'finger',
                    'items': [{'key': 'BUILDBOT_DISK_GEN', 'value': '2'}]
               },
                'disks': []
           })
        createDisk = self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/disks',
            json={
                'sourceImage': 'projects/p/global/images/im',
                'name': 'i-3',  # BUILDBOT_DISK_GEN + 1
                'type': 'projects/p/zones/z/diskTypes/pd-ssd'
           })
        expected_json = {
            'fingerprint': 'finger',
            'items': [
                {'key': 'BUILDBOT_DISK_GEN', 'value': '3'},
                {'key': 'WORKERNAME', 'value': 'test'},
                {'key': 'WORKERPASS', 'value': 'password'},
                {'key': 'BUILDMASTER', 'value': 'master'},
                {'key': 'BUILDMASTER_PORT', 'value': '5050'}
            ],
            'kind': 'compute#metadata'
        }
        setMetadata = self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/setMetadata',
            json=lambda j: self.compareMetadata(expected_json, j))
        self.gce.expectWaitForOperation(createDisk)
        attachDisk = self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/attachDisk',
            json={
                'boot': True,
                'source': '/compute/v1/projects/p/zones/z/disks/i-3',
                'deviceName': 'i-3',
                'index': 0
           })
        self.gce.expectWaitForOperation(attachDisk)
        self.gce.expectWaitForOperation(setMetadata)
        self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/start')
        self.gce.expectInstanceStateWait('RUNNING')

        result = yield self.worker.start_instance(FakeBuild())
        self.assertTrue(result)

    @defer.inlineCallbacks
    def test_stop_instance_nominal_flow(self):
        self.gce.expect('GET', '/compute/v1/projects/p/zones/z/instances/i',
            result={
                'status': 'RUNNING',
                'metadata': {
                    'fingerprint': 'finger',
                    'items': [{'key': 'BUILDBOT_DISK_GEN', 'value': 2}]
               },
                'disks': [{'boot': True, 'deviceName': 'current-boot'}]
           })
        self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/stop')
        self.gce.expectInstanceStateWait('TERMINATED')

        detachDisk = self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/detachDisk',
            params={'deviceName': 'current-boot'})

        setMetadata = self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/setMetadata',
            json={
                'fingerprint': 'finger',
                'items': [{'key': 'BUILDBOT_DISK_GEN', 'value': '3'}],
                'kind': 'compute#metadata'
            })
        createDisk = self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/disks',
            json={
                'sourceImage': 'projects/p/global/images/im',
                'name': 'i-3',  # BUILDBOT_DISK_GEN + 1
                'type': 'projects/p/zones/z/diskTypes/pd-ssd'
           })
        self.gce.expectWaitForOperation(createDisk)

        self.gce.expectWaitForOperation(detachDisk)
        self.gce.expectOperationRequest(
            'DELETE', '/compute/v1/projects/p/zones/z/disks/current-boot')
        attachDisk = self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/attachDisk',
            json={
                'boot': True,
                'source': '/compute/v1/projects/p/zones/z/disks/i-3',
                'deviceName': 'i-3',
                'index': 0
           })
        self.gce.expectWaitForOperation(attachDisk)
        self.gce.expectWaitForOperation(setMetadata)

        self.gce.expect('GET', '/compute/v1/projects/p/zones/z/instances/i',
            result={
                'metadata': {
                    'fingerprint': 'finger2',
                    'items': [{'key': 'BUILDBOT_DISK_GEN', 'value': '3'}]
               }
           })

        expected_json = {
            'fingerprint': 'finger2',
            'items': [
                {'key': 'BUILDBOT_DISK_GEN', 'value': '3'},
                {'key': 'BUILDBOT_CLEAN', 'value': '1'}
            ],
            'kind': 'compute#metadata'
        }
        setMetadata = self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/setMetadata',
            json=lambda j: self.compareMetadata(expected_json, j))
        self.gce.expectWaitForOperation(setMetadata)

        yield self.worker.stop_instance()

    @defer.inlineCallbacks
    def test_stop_instance_does_nothing_if_stopInstanceOnStop_is_false(self):
        self.worker.stopInstanceOnStop = False
        yield self.worker.stop_instance()

    @defer.inlineCallbacks
    def test_stop_instance_only_stops_if_resetDisk_is_false(self):
        self.worker.resetDisk = False

        self.gce.expect('GET', '/compute/v1/projects/p/zones/z/instances/i',
            result={
                'status': 'RUNNING',
                'metadata': {
                    'fingerprint': 'finger',
                    'items': [{'key': 'BUILDBOT_DISK_GEN', 'value': 2}]
                },
                'disks': [{'boot': True, 'deviceName': 'current-boot'}]
            })
        self.gce.expectOperationRequest(
            'POST', '/compute/v1/projects/p/zones/z/instances/i/stop')
        self.gce.expectInstanceStateWait('TERMINATED')

        yield self.worker.stop_instance()
