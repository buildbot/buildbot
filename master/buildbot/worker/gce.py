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

GCE_NODE_METADATA_KEYS = ('WORKERNAME', 'WORKERPASS', 'BUILDMASTER', 'BUILDMASTER_PORT')

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
        project=None, zone=None, instance=None,
        sa_credentials=None,
        password=None, masterFQDN=None, **kwargs):

        if project is None or zone is None or instance is None:
            config.error("need to provide project, zone and instance name")
        if sa_credentials is None:
            config.error("need to provide Service Account credentials")
        if instance is not None and not isinstance(instance, str):
            if not hasattr(instance, 'getRenderingFor'):
                config.error("instance must be a string")

        if password is None:
            password = self.getRandomPass()

        AbstractLatentWorker.checkConfig(self, name, password, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(self, name, password=None,
        project=None, zone=None, instance=None,
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
        self.sa_credentials = sa_credentials
        self._gce = yield gceclientservice.GCEClientService.getService(
            self.master, ['https://www.googleapis.com/auth/compute'],
            sa_credentials, renderer=self)
        AbstractLatentWorker.reconfigService(self, name, password, **kwargs)
        return defer.returnValue(True)

    def instanceEndpoint(self, method=None):
        if method:
            return "/compute/v1/projects/{0}/zones/{1}/instances/{2}/{3}".format(
                self.project, self.zone, self.instance, method)
        else:
            return "/compute/v1/projects/{0}/zones/{1}/instances/{2}".format(
                self.project, self.zone, self.instance)

    @defer.inlineCallbacks
    def getInstanceState(self):
        url = self.instanceEndpoint()
        res = yield self._gce.get(url)
        info = yield self.validateRes(res, url=url)
        return defer.returnValue(info)

    def getDesiredMetadata(self, build, existingMetadata=[]):
        result = [x for x in existingMetadata if x['key'] not in GCE_NODE_METADATA_KEYS]
        result.extend([
            {"key": "WORKERNAME", "value": self.name},
            {"key": "WORKERPASS", "value": self.password}
        ])
        if ":" in self.masterFQDN:
            host, port = self.masterFQDN.split(":")
            result.append({"key": "BUILDMASTER", "value": host})
            result.append({"key": "BUILDMASTER_PORT", "value": port})
        else:
            result.append({"key": "BUILDMASTER", "value": self.masterFQDN})
        return result

    @defer.inlineCallbacks
    def setMetadata(self, fingerprint, metadata):
        res = yield self._gce.post(self.instanceEndpoint("setMetadata"), json={
            "fingerprint": fingerprint,
            "items": metadata,
            "kind": "compute#metadata"
        })
        res = yield self.validateRes(res)
        return defer.returnValue(res)

    @defer.inlineCallbacks
    def ensureInstanceStopped(self, instance_state):
        while instance_state['status'] not in ('STOPPED', 'TERMINATED'):
            if instance_state['status'] in ('RUNNING', 'SUSPENDING', 'SUSPENDED'):
                yield self._gce.post(self.instanceEndpoint("stop"))

            time.sleep(0.01)
            instance_state = yield self.getInstanceState()

        return defer.returnValue(instance_state)

    @defer.inlineCallbacks
    def ensureInstanceStarted(self, instance_state):
        while instance_state['status'] not in ("RUNNING"):
            if instance_state['status'] not in ("TERMINATED", "PROVISIONING", "STAGING"):
                raise RuntimeError("Failed to start instance: is in state {0}".
                    format(instance_state['status']))

            time.sleep(0.01)
            instance_state = yield self.getInstanceState()

        return defer.returnValue(instance_state)

    @defer.inlineCallbacks
    def start_instance(self, build):
        instance_state = yield self.getInstanceState()
        instance_state = yield self.ensureInstanceStopped(instance_state)

        fingerprint = instance_state['metadata']['fingerprint']
        metadata = self.getDesiredMetadata(build)
        yield self.setMetadata(fingerprint, metadata)

        res = yield self._gce.post(self.instanceEndpoint("start"))
        yield self.validateRes(res)
        instance_state = yield self.getInstanceState()
        yield self.ensureInstanceStarted(instance_state)
        return defer.returnValue(True)

    @defer.inlineCallbacks
    def stop_instance(self, build):
        instance_state = yield self.getInstanceState()
        yield self.ensureInstanceStopped(instance_state)
        return defer.returnValue(None)

    @defer.inlineCallbacks
    def validateRes(self, res, url=None):
        try:
            res_json = yield res.json()
        except json.decoder.JSONDecodeError:
            message = yield res.content()
            res_json = {'error':{'message': message}}
            raise GCEError(res_json, url=url)

        if res.code not in (200, 201, 202):
            raise GCEError(res_json, url=url)
        return defer.returnValue(res_json)
