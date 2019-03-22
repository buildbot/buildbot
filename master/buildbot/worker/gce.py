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

from twisted.internet import defer

from buildbot import config
from buildbot.util import gceclientservice
from buildbot.util.logger import Logger
from buildbot.worker import AbstractLatentWorker

log = Logger()

GCE_NODE_METADATA_KEYS = (
    'WORKERNAME', 'WORKERPASS',
    'BUILDMASTER', 'BUILDMASTER_PORT',
    'BUILDBOT_CLEAN'
)

DISK_NAME_GEN_KEY = "BUILDBOT_DISK_GEN"


class GCELatentWorker(AbstractLatentWorker):
    name = "GCELatentWorker"

    def checkConfig(self, name, project=None, zone=None, instance=None, image=None,
                    stopInstanceOnStop=True, resetDisk=True, useSSD=True,
                    sa_credentials=None, password=None, masterFQDN=None, **kwargs):

        if project is None or zone is None or instance is None:
            config.error("need to provide project, zone and instance name")
        if sa_credentials is None:
            config.error("need to provide Service Account credentials")
        if image is None:
            config.error("need to provide a base disk image")

        if password is None:
            password = self.getRandomPass()

        AbstractLatentWorker.checkConfig(self, name, password, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(self, name, password=None, project=None, zone=None,
                        instance=None, image=None, stopInstanceOnStop=True,
                        resetDisk=True, useSSD=True, sa_credentials=None,
                        masterFQDN=None, **kwargs):

        if password is None:
            password = self.getRandomPass()
        if masterFQDN is None:
            masterFQDN = socket.getfqdn()
        self.masterFQDN = masterFQDN
        self.project = project
        self.zone = zone
        self.instance = instance
        self.image = image
        self.resetDisk = resetDisk
        self.useSSD = useSSD
        self.stopInstanceOnStop = stopInstanceOnStop
        self.sa_credentials = sa_credentials
        self._gce = yield self.getGCEService(sa_credentials)
        result = yield AbstractLatentWorker.reconfigService(self, name, password, **kwargs)
        return result

    @defer.inlineCallbacks
    def getGCEService(self, sa_credentials):
        gce = yield gceclientservice.GCEClientService.getService(
            self.master, ['https://www.googleapis.com/auth/compute'], sa_credentials,
            project=self.project, zone=self.zone, instance=self.instance,
            renderer=self)
        return gce

    def resetClientService(self, gce):
        self._gce = gce

    def getMetadataFromState(self, state):
        metadata = state['metadata']
        dict = {}
        for x in metadata.get('items', []):
            dict[x['key']] = x['value']
        return (metadata['fingerprint'], dict)

    def getDesiredMetadata(self, build):
        if ":" in self.masterFQDN:
            host, port = self.masterFQDN.split(":")
        else:
            host = self.masterFQDN
            port = 9989

        return {
            "WORKERNAME": self.name,
            "WORKERPASS": self.password,
            "BUILDMASTER": host,
            "BUILDMASTER_PORT": port
        }

    def updateMetadata(self, build, metadata):
        result = metadata.copy()
        for key in GCE_NODE_METADATA_KEYS:
            result.pop(key, None)
        result.update(self.getDesiredMetadata(build))
        return result

    def getMetadataItemsFromDict(self, metadata):
        return [{"key": key, "value": metadata[key]} for key in metadata]

    def setMetadata(self, fingerprint, metadata):
        return self._gce.setMetadata(fingerprint=fingerprint,
            items=self.getMetadataItemsFromDict(metadata))

    def getCurrentDiskName(self, disks):
        for d in disks:
            if d['boot']:
                return d['deviceName']

    def getNewDiskName(self, metadata):
        gen = int(metadata.get(DISK_NAME_GEN_KEY, 0)) + 1
        metadata[DISK_NAME_GEN_KEY] = str(gen)
        return "{0}-{1}".format(self.instance, gen)

    def createBootDisk(self, disk_name):
        if self.useSSD:
            diskType = "pd-ssd"
        else:
            diskType = "pd-standard"

        return self._gce.createDisk(image=self.image, name=disk_name, type=diskType)

    @defer.inlineCallbacks
    def start_instance(self, build):
        instance_state = yield self._gce.getInstanceState()

        fingerprint, metadata = self.getMetadataFromState(instance_state)
        updated_metadata = self.updateMetadata(build, metadata)

        instance_stop = None
        if instance_state['status'] not in ('STOPPED', 'TERMINATED'):
            if self.stopInstanceOnStop:
                # Should not have happened ... warn the user
                log.warn(("gce: {0} is unexpectedly running. Either buildbot failed to stop it "
                    "on the last stop, or the node was started externally. Requesting stop").format(self.instance))
            else:
                log.info("gce: {0} is running (stopInstanceOnStop=False), requesting stop".format(self.instance))

            instance_stop = self._gce.instanceStop()

        if not self.resetDisk:
            metadata['BUILDBOT_CLEAN'] = '1'

        boot_disk_create = None
        if 'BUILDBOT_CLEAN' not in metadata:
            if self.resetDisk:
                log.warn("gce: it seems that {0} was not reset after the last build as it should have, will do it now".format(
                    self.instance))
            else:
                log.info("gce: {0} has not been reset on stop (resetDisk=False), will do it now".format(self.instance))

            boot_disk_name = self.getNewDiskName(updated_metadata)
            boot_disk_create = self.createBootDisk(boot_disk_name)

        metadata_set = self.setMetadata(fingerprint, updated_metadata)

        if instance_stop is not None:
            if self.stopInstanceOnStop:
                log.info("gce: waiting for {0} to be stopped".format(self.instance))
            else:
                log.warn("gce: waiting for {0} to be stopped".format(self.instance))
            yield self._gce.waitInstanceState('TERMINATED')

        if boot_disk_create is not None:
            current_disk_name = self.getCurrentDiskName(instance_state['disks'])
            if current_disk_name:
                log.info("gce: detaching {0} from {1}".format(
                    current_disk_name, self.instance))
                yield self._gce.waitForOperation(self._gce.detachDisk(current_disk_name))
                log.info("gce: deleting {0}".format(current_disk_name))
                yield self._gce.deleteDisk(current_disk_name)

            log.info("gce: waiting for fresh disk {0} to be created for {1}".format(
                boot_disk_name, self.instance))
            yield self._gce.waitForOperation(boot_disk_create)

            log.info("gce: attaching new disk {0} to {1}".format(
                boot_disk_name, self.instance))
            yield self._gce.waitForOperation(
                self._gce.attachDisk(boot_disk_name, index=0, boot=True))

        log.info("gce: starting {0}".format(self.instance))
        yield self._gce.waitForOperation(metadata_set)
        yield self._gce.instanceStart()
        yield self._gce.waitInstanceState('RUNNING')
        return True

    @defer.inlineCallbacks
    def stop_instance(self, fast=False):
        if not self.stopInstanceOnStop:
            log.info("gce: not stopping {0}: stopInstanceOnStop == False".format(
                self.instance))
            return None

        state = yield self._gce.getInstanceState()
        if state['status'] not in ('TERMINATED',):
            log.info("gce: stopping {0}".format(self.instance))
            yield self._gce.instanceStop()
            # We don't use waitOperationEnd here as there is as much as ~55s
            # between the instance state switching to TERMINATED and the
            # operation reporting to be DONE
            #
            # Since it is possible to manipulate the instance after the
            # state changed, save 55s each time
            yield self._gce.waitInstanceState('TERMINATED')

        if self.resetDisk:
            log.info("gce: resetting the boot disk of {0}".format(self.instance))
            fingerprint, metadata = self.getMetadataFromState(state)
            boot_disk_name = self.getNewDiskName(metadata)
            current_disk_name = self.getCurrentDiskName(state['disks'])
            detach_disk = self._gce.detachDisk(current_disk_name)
            # Update the GEN metadata key right now, so that we can generate
            # a new boot disk without conflict if something wrong happens
            metadata_set = self.setMetadata(fingerprint, metadata)
            yield self._gce.waitForOperation(self.createBootDisk(boot_disk_name))

            yield self._gce.waitForOperation(detach_disk)
            yield self._gce.deleteDisk(current_disk_name)
            yield self._gce.waitForOperation(
                self._gce.attachDisk(boot_disk_name, index=0, boot=True))
            yield self._gce.waitForOperation(metadata_set)

            # Finally, mark as clean
            instance_state = yield self._gce.getInstanceState()
            fingerprint, metadata = self.getMetadataFromState(instance_state)
            metadata['BUILDBOT_CLEAN'] = '1'
            yield self._gce.waitForOperation(self.setMetadata(fingerprint, metadata))

        return None
