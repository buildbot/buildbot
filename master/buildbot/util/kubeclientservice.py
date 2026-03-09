# This file is part of Buildbot. Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members
from __future__ import annotations

import abc
import base64
import os
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet.error import ProcessExitedAlready
from twisted.logger import Logger
from twisted.python.failure import Failure

from buildbot import config
from buildbot.util import service
from buildbot.util.protocol import LineProcessProtocol

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType
log = Logger()


# this is a BuildbotService, so that it can be started and destroyed.
# this is needed to implement kubectl proxy lifecycle
class KubeConfigLoaderBase(service.BuildbotService):
    name = "KubeConfig"

    @abc.abstractmethod
    def getConfig(self) -> dict[str, Any]:
        """
        @return dictionary with optional params
        {
            'master_url': 'https://kube_master.url',
            'namespace': 'default_namespace',
            'headers' {
                'Authentication': XXX
            }
            # todo (quite hard to implement with treq):
            'cert': 'optional client certificate used to connect to ssl'
            'verify': 'kube master certificate authority to use to connect'
        }
        """

    def get_master_url(self) -> str:
        # This function may be called before reconfigService() is called.
        # The function must be overridden in case getConfig() is not fully setup in such situation.
        return self.getConfig()["master_url"]

    def getAuthorization(self) -> Any:
        return None

    def __str__(self) -> str:
        """return unique str for SharedService"""
        # hash is implemented from ComparableMixin
        return f"{self.__class__.__name__}({hash(self)})"


class KubeHardcodedConfig(KubeConfigLoaderBase):
    def reconfigService(
        self,
        master_url: str | None = None,
        bearerToken: Any = None,
        basicAuth: Any = None,
        headers: dict[str, str] | None = None,
        cert: Any = None,
        verify: Any = None,
        namespace: str = "default",
    ) -> None:
        self.config: dict[str, Any] = {
            'master_url': master_url,
            'namespace': namespace,
            'headers': {},
        }
        if headers is not None:
            self.config['headers'] = headers
        if basicAuth and bearerToken:
            raise RuntimeError("set one of basicAuth and bearerToken, not both")
        self.basicAuth = basicAuth
        self.bearerToken = bearerToken
        if cert is not None:
            self.config['cert'] = cert
        if verify is not None:
            self.config['verify'] = verify

    checkConfig = reconfigService

    @defer.inlineCallbacks
    def getAuthorization(self) -> InlineCallbacksType[str | None]:
        if self.basicAuth is not None:
            basicAuth = yield self.renderSecrets(self.basicAuth)
            authstring = f"{basicAuth['user']}:{basicAuth['password']}".encode()
            encoded = base64.b64encode(authstring)
            return f"Basic {encoded}"  # type: ignore[str-bytes-safe]

        if self.bearerToken is not None:
            bearerToken = yield self.renderSecrets(self.bearerToken)
            return f"Bearer {bearerToken}"

        return None

    def getConfig(self) -> dict[str, Any]:
        return self.config


class KubeCtlProxyConfigLoader(KubeConfigLoaderBase):
    """We use kubectl proxy to connect to kube master.
    Parsing the config and setting up SSL is complex.
    So for now, we use kubectl proxy to load the config and connect to master.
    This will run the kube proxy as a subprocess, and return configuration with
    http://localhost:PORT
    """

    kube_ctl_proxy_cmd = ['kubectl', 'proxy']  # for tests override

    class LocalPP(LineProcessProtocol):
        def __init__(self) -> None:
            super().__init__()
            self.got_output_deferred: defer.Deferred[bytes] = defer.Deferred()
            self.terminated_deferred: defer.Deferred[None] = defer.Deferred()
            self.first_line = b""

        def outLineReceived(self, line: bytes) -> None:
            if not self.got_output_deferred.called:
                self.got_output_deferred.callback(line)

        def errLineReceived(self, line: bytes) -> None:
            if not self.got_output_deferred.called:
                self.got_output_deferred.errback(Failure(RuntimeError(line)))

        def processEnded(self, status: Failure) -> None:
            super().processEnded(status)
            self.terminated_deferred.callback(None)

    def checkConfig(self, proxy_port: int = 8001, namespace: str = "default") -> None:
        self.proxy_port = proxy_port
        self.namespace = namespace
        self.pp: KubeCtlProxyConfigLoader.LocalPP | None = None
        self.process: Any = None

    @defer.inlineCallbacks
    def ensure_subprocess_killed(self) -> InlineCallbacksType[None]:
        if self.pp is not None:
            try:
                self.process.signalProcess("TERM")
            except ProcessExitedAlready:
                pass  # oh well
            yield self.pp.terminated_deferred

    @defer.inlineCallbacks
    def reconfigService(
        self, proxy_port: int = 8001, namespace: str = "default"
    ) -> InlineCallbacksType[None]:
        self.proxy_port = proxy_port
        self.namespace = namespace

        if self.running:
            yield self.ensure_subprocess_killed()
            yield self.start_subprocess()

    @defer.inlineCallbacks
    def start_subprocess(self) -> InlineCallbacksType[None]:
        self.pp = self.LocalPP()
        self.process = reactor.spawnProcess(  # type: ignore[attr-defined]
            self.pp,
            self.kube_ctl_proxy_cmd[0],
            [*self.kube_ctl_proxy_cmd, "-p", str(self.proxy_port)],
            env=os.environ,
        )
        self.kube_proxy_output = yield self.pp.got_output_deferred

    @defer.inlineCallbacks
    def startService(self) -> InlineCallbacksType[None]:
        try:
            yield self.start_subprocess()
        except Exception:
            yield self.ensure_subprocess_killed()
            raise
        yield super().startService()

    @defer.inlineCallbacks
    def stopService(self) -> InlineCallbacksType[None]:
        yield self.ensure_subprocess_killed()
        yield super().stopService()

    def getConfig(self) -> dict[str, Any]:
        return {'master_url': f"http://localhost:{self.proxy_port}", 'namespace': self.namespace}


class KubeInClusterConfigLoader(KubeConfigLoaderBase):
    kube_dir = '/var/run/secrets/kubernetes.io/serviceaccount/'

    kube_namespace_file = os.path.join(kube_dir, 'namespace')
    kube_token_file = os.path.join(kube_dir, 'token')
    kube_cert_file = os.path.join(kube_dir, 'ca.crt')

    def checkConfig(self) -> None:
        if not os.path.exists(self.kube_dir):
            config.error(f"Not in kubernetes cluster (kube_dir not found: {self.kube_dir})")

    def reconfigService(self) -> None:  # type: ignore[override]
        self.config: dict[str, Any] = {}
        self.config['master_url'] = self.get_master_url()
        self.config['verify'] = self.kube_cert_file
        with open(self.kube_token_file, encoding="utf-8") as token_content:
            token = token_content.read().strip()
            self.config['headers'] = {'Authorization': f'Bearer {token}'.format(token)}
        with open(self.kube_namespace_file, encoding="utf-8") as namespace_content:
            self.config['namespace'] = namespace_content.read().strip()

    def getConfig(self) -> dict[str, Any]:
        return self.config

    def get_master_url(self) -> str:
        return os.environ["KUBERNETES_PORT"].replace("tcp", "https")


class KubeClientService(service.SharedService):
    name: str | None = "KubeClientService"  # type: ignore[assignment]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._config_id_to_workers: dict[int, list[str]] = {}
        self._worker_to_config: dict[str, KubeConfigLoaderBase] = {}
        self._lock = defer.DeferredLock()

    @defer.inlineCallbacks
    def register(self, worker: Any, config: KubeConfigLoaderBase) -> InlineCallbacksType[None]:
        yield self._lock.acquire()
        try:
            if worker.name in self._worker_to_config:
                raise ValueError(f"Worker {worker.name} registered multiple times")
            self._worker_to_config[worker.name] = config
            config_id = id(config)
            if config_id in self._config_id_to_workers:
                self._config_id_to_workers[config_id].append(worker.name)
            else:
                self._config_id_to_workers[config_id] = [worker.name]
                yield config.setServiceParent(self)
        finally:
            self._lock.release()

    @defer.inlineCallbacks
    def unregister(self, worker: Any) -> InlineCallbacksType[None]:
        yield self._lock.acquire()
        try:
            if worker.name not in self._worker_to_config:
                raise ValueError(f"Worker {worker.name} was not registered")
            config = self._worker_to_config.pop(worker.name)
            config_id = id(config)
            worker_list = self._config_id_to_workers[config_id]
            worker_list.remove(worker.name)
            if not worker_list:
                del self._config_id_to_workers[config_id]
                yield config.disownServiceParent()
        finally:
            self._lock.release()

    @defer.inlineCallbacks
    def startService(self) -> InlineCallbacksType[None]:
        yield self._lock.acquire()
        try:
            yield super().startService()
        finally:
            self._lock.release()

    @defer.inlineCallbacks
    def stopService(self) -> InlineCallbacksType[None]:
        yield self._lock.acquire()
        try:
            yield super().stopService()
        finally:
            self._lock.release()
