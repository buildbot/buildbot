import json
import jwt
import socket
import time

from twisted.internet import defer

from buildbot import config
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
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

class GCEError(RuntimeError):
    def __init__(self, response_json, url=None):
        message = response_json['error']['message']
        if url is not None:
            message = "{0}: {1}".format(url, message)

        RuntimeError.__init__(self, message)
        self.json = response_json
        self.reason = response_json.get('error')

class GCELatentWorker(AbstractLatentWorker):
    name = "GCELatentWorker"

    def checkConfig(self, name,
        project=None, zone=None, instance=None, image=None,
        sa_credentials=None,
        password=None, masterFQDN=None, **kwargs):

        if project is None or zone is None or instance is None:
            config.error("need to provide project, zone and instance name")
        if sa_credentials is None:
            config.error("need to provide Service Account credentials")
        if instance is not None and not isinstance(instance, str):
            if not hasattr(instance, 'getRenderingFor'):
                config.error("instance must be a string")
        if image is None:
            config.error("must provide a base disk image")

        if password is None:
            password = self.getRandomPass()

        AbstractLatentWorker.checkConfig(self, name, password, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(self, name, password=None,
        project=None, zone=None, instance=None, image=None,
        sa_credentials=None,
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
        self.sa_credentials = sa_credentials
        self._gce = yield gceclientservice.GCEClientService.getService(
            self.master, ['https://www.googleapis.com/auth/compute'],
            sa_credentials, renderer=self)
        AbstractLatentWorker.reconfigService(self, name, password, **kwargs)
        return defer.returnValue(True)

    def zoneEndpoint(self, method=None):
        base = "/compute/v1/projects/{0}/zones/{1}".format(
            self.project, self.zone)
        if method:
            return "{0}/{1}".format(base, method)
        else:
            return base

    def instanceEndpoint(self, method=None):
        rel = "instances/{0}".format(self.instance)
        if method:
            rel = "{0}/{1}".format(rel, method)
        return self.zoneEndpoint(rel)

    def processRequest(self, deferred):
        return self.validateRes(deferred)

    @defer.inlineCallbacks
    def processAsyncRequest(self, deferred):
        op = yield self.validateRes(deferred)
        yield self.waitOperationEnd(op)

    def getInstanceState(self, fields=None):
        if fields is None:
            return self._gce.get(self.instanceEndpoint())
        else:
            return self._gce.get(self.instanceEndpoint(),
                params={'fields': fields})

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
        return self._gce.post(self.instanceEndpoint("setMetadata"), json={
            "fingerprint": fingerprint,
            "items": self.getMetadataItemsFromDict(metadata),
            "kind": "compute#metadata"
        })

    def getCurrentDiskName(self, disks):
        for d in disks:
            if d['boot']:
                return d['deviceName']

    def getNewDiskName(self, metadata):
        gen = int(metadata.get(DISK_NAME_GEN_KEY, 0)) + 1
        metadata[DISK_NAME_GEN_KEY] = str(gen)
        return "{0}-{1}".format(self.instance, gen)

    def createBootDisk(self, disk_name):
        return self._gce.post(self.zoneEndpoint("disks"),
            json={
                "sourceImage": self.image,
                "name": disk_name
            }
        )

    def attachBootDisk(self, disk_name):
        return self._gce.post(
            self.instanceEndpoint("attachDisk"),
            json={
                "boot": True,
                "source": self.zoneEndpoint("disks/{0}".format(disk_name)),
                "deviceName": disk_name,
                "index": 0
            }
        )

    def detachBootDisk(self, diskName):
        return self._gce.post(
            self.instanceEndpoint("detachDisk"),
            params={"deviceName": diskName}
        )

    @defer.inlineCallbacks
    def waitInstanceState(self, desiredState):
        state = yield self.processRequest(self.getInstanceState(fields='status'))
        while state['status'] != desiredState:
            time.sleep(0.1)
            state = yield self.processRequest(self.getInstanceState(fields='status'))

    @defer.inlineCallbacks
    def waitOperationEnd(self, op):
        while op['status'] != 'DONE':
            time.sleep(0.1)
            op = self._gce.get(op['selfLink'])
            op = yield self.validateRes(op)

        if 'error' in op:
            raise GCEError(op['error'])

    @defer.inlineCallbacks
    def start_instance(self, build):
        instance_state = yield self.processRequest(self.getInstanceState())

        fingerprint, metadata = self.getMetadataFromState(instance_state)
        updated_metadata = self.updateMetadata(build, metadata)

        instance_stop = None
        if instance_state['status'] not in ('STOPPED', 'TERMINATED'):
            log.info("gce: {0} is running, requesting stop".format(
                self.instance))
            instance_stop = self._gce.post(self.instanceEndpoint("stop"))


        boot_disk_create = None
        if 'BUILDBOT_CLEAN' not in metadata:
            log.info("gce: {0} has not been reset on stop, will do it now".format(
                self.instance))
            boot_disk_name   = self.getNewDiskName(updated_metadata)
            boot_disk_create = self.createBootDisk(boot_disk_name)

        metadata_set = self.setMetadata(fingerprint, updated_metadata)

        if instance_stop is not None:
            log.info("gce: waiting for {0} to be stopped".format(self.instance))
            yield self.processRequest(instance_stop)
            yield self.waitInstanceState('TERMINATED')

        if boot_disk_create is not None:
            current_disk_name = self.getCurrentDiskName(instance_state['disks'])
            if current_disk_name:
                log.info("gce: detaching {0} from {1}".format(
                    current_disk_name, self.instance))
                yield self.processAsyncRequest(self.detachBootDisk(current_disk_name))

            log.info("gce: waiting for fresh disk {0} to be created for {1}".format(
                boot_disk_name, self.instance))
            yield self.processAsyncRequest(boot_disk_create)

            log.info("gce: attaching new disk {0} to {1}".format(
                boot_disk_name, self.instance))
            yield self.processAsyncRequest(
                self.attachBootDisk(boot_disk_name))

        log.info("gce: starting {0}".format(self.instance))
        yield self.processAsyncRequest(metadata_set)
        yield self.processRequest(
            self._gce.post(self.instanceEndpoint("start")))
        yield self.waitInstanceState('RUNNING')
        return defer.returnValue(True)

    @defer.inlineCallbacks
    def stop_instance(self, build):
        state = yield self.processRequest(self.getInstanceState())
        if state['status'] not in ('STOPPED', 'TERMINATED'):
            yield self.processAsyncRequest(
                self._gce.post(self.instanceEndpoint("stop")))

        return defer.returnValue(None)

    @defer.inlineCallbacks
    def validateRes(self, res, url=None):
        try:
            res = yield res
            res_json = yield res.json()
        except json.decoder.JSONDecodeError:
            message = yield res.content()
            res_json = {'error':{'message': message}}
            raise GCEError(res_json, url=url)

        if res.code not in (200, 201, 202):
            raise GCEError(res_json, url=url)
        return defer.returnValue(res_json)
