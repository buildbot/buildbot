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

from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer
from twisted.logger import Logger

from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.util import asyncSleep
from buildbot.util import httpclientservice
from buildbot.util import kubeclientservice
from buildbot.util.latent import CompatibleLatentWorkerMixin
from buildbot.worker.docker import DockerBaseWorker

if TYPE_CHECKING:
    from collections.abc import Callable

    from buildbot.interfaces import IHttpResponse
    from buildbot.process.properties import Properties
    from buildbot.util.kubeclientservice import KubeConfigLoaderBase
    from buildbot.util.twisted import InlineCallbacksType

log = Logger()


class KubeError(RuntimeError):
    pass


class KubeJsonError(KubeError):
    def __init__(self, code: int, response_json: dict[str, Any]) -> None:
        super().__init__(response_json['message'])
        self.code = code
        self.json = response_json
        self.reason = response_json.get('reason')


class KubeTextError(KubeError):
    def __init__(self, code: int, response: str) -> None:
        super().__init__(response)
        self.code = code


class KubeLatentWorker(CompatibleLatentWorkerMixin, DockerBaseWorker):
    instance = None
    _namespace: str | None = None
    _kube = None
    _kube_config: KubeConfigLoaderBase | None = None

    @defer.inlineCallbacks
    def getPodSpec(self, build: Properties) -> InlineCallbacksType[dict[str, Any]]:
        image = yield build.render(self.image)
        env = yield self.createEnvironment(build)

        return {
            "apiVersion": "v1",
            "kind": "Pod",
            "metadata": {"name": self.getContainerName()},
            "spec": {
                "affinity": (yield self.get_affinity(build)),
                "containers": [
                    {
                        "name": self.getContainerName(),
                        "image": image,
                        "env": [{"name": k, "value": v} for k, v in env.items()],
                        "resources": (yield self.getBuildContainerResources(build)),
                        "volumeMounts": (yield self.get_build_container_volume_mounts(build)),
                    }
                ]
                + (yield self.getServicesContainers(build)),
                "nodeSelector": (yield self.get_node_selector(build)),
                "restartPolicy": "Never",
                "volumes": (yield self.get_volumes(build)),
            },
        }

    def getBuildContainerResources(self, build: Properties) -> dict[str, Any]:
        # customization point to generate Build container resources
        return {}

    def get_build_container_volume_mounts(self, build: Properties) -> list[Any]:
        return []

    def get_affinity(self, build: Properties) -> dict[str, Any]:
        return {}

    def get_node_selector(self, build: Properties) -> dict[str, Any]:
        return {}

    def get_volumes(self, build: Properties) -> list[Any]:
        return []

    def getServicesContainers(self, build: Properties) -> list[Any]:
        # customization point to create services containers around the build container
        # those containers will run within the same localhost as the build container (aka within
        # the same pod)
        return []

    def renderWorkerProps(self, build_props: Properties) -> Any:
        return self.getPodSpec(build_props)

    def checkConfig(  # type: ignore[override]
        self,
        name: str,
        image: str = 'buildbot/buildbot-worker',
        namespace: str | None = None,
        masterFQDN: str | Callable[[], str] | None = None,
        master_protocol: str = 'pb',
        kube_config: KubeConfigLoaderBase | None = None,
        **kwargs: Any,
    ) -> None:
        super().checkConfig(name, None, master_protocol=master_protocol, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(  # type: ignore[override]
        self,
        name: str,
        image: str = 'buildbot/buildbot-worker',
        namespace: str | None = None,
        masterFQDN: str | Callable[[], str] | None = None,
        master_protocol: str = 'pb',
        kube_config: KubeConfigLoaderBase | None = None,
        **kwargs: Any,
    ) -> InlineCallbacksType[None]:
        # Set build_wait_timeout to 0 if not explicitly set: Starting a
        # container is almost immediate, we can afford doing so for each build.
        if 'build_wait_timeout' not in kwargs:
            kwargs['build_wait_timeout'] = 0
        if masterFQDN is None:
            masterFQDN = self.get_ip
        if callable(masterFQDN):
            masterFQDN = masterFQDN()

        self._http = yield httpclientservice.HTTPSession(
            self.master.httpservice,
            kube_config.get_master_url(),  # type: ignore[union-attr]
        )

        if self.running and self._kube is not None:
            yield self._kube.unregister(self)

        self._kube = yield kubeclientservice.KubeClientService.getService(self.master)
        self._kube_config = kube_config

        if self.running:
            yield self._kube.register(self, kube_config)

        self._namespace = namespace or kube_config.getConfig()['namespace']  # type: ignore[union-attr]

        yield super().reconfigService(
            name, image=image, masterFQDN=masterFQDN, master_protocol=master_protocol, **kwargs
        )

    @defer.inlineCallbacks
    def startService(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        yield super().startService()
        yield self._kube.register(self, self._kube_config)  # type: ignore[union-attr]

    @defer.inlineCallbacks
    def stopService(self) -> InlineCallbacksType[None]:
        yield self._kube.unregister(self)  # type: ignore[union-attr]
        yield super().stopService()

    @defer.inlineCallbacks
    def start_instance(self, build: Properties) -> InlineCallbacksType[bool]:
        try:
            yield self.stop_instance(reportFailure=False)
            pod_spec = yield self.renderWorkerPropsOnStart(build)
            yield self._create_pod(self._namespace, pod_spec)  # type: ignore[arg-type]
        except KubeError as e:
            raise LatentWorkerFailedToSubstantiate(str(e)) from e
        return True

    @defer.inlineCallbacks
    def stop_instance(  # type: ignore[override]
        self, fast: bool = False, reportFailure: bool = True
    ) -> InlineCallbacksType[None]:
        self.current_pod_spec = None
        self.resetWorkerPropsOnStop()
        try:
            yield self._delete_pod(self._namespace, self.getContainerName())  # type: ignore[arg-type]
        except KubeJsonError as e:
            if reportFailure and e.reason != 'NotFound':
                raise
        if fast:
            return
        yield self._wait_for_pod_deletion(
            self._namespace,  # type: ignore[arg-type]
            self.getContainerName(),
            timeout=self.missing_timeout,  # type: ignore[arg-type]
        )

    @defer.inlineCallbacks
    def _get_request_kwargs(self) -> InlineCallbacksType[dict[str, Any]]:
        config = self._kube_config.getConfig()  # type: ignore[union-attr]

        kwargs: dict[str, Any] = {}

        if config.get("headers"):
            kwargs.setdefault("headers", {}).update(config["headers"])

        auth = yield self._kube_config.getAuthorization()  # type: ignore[union-attr]
        if auth is not None:
            kwargs.setdefault("headers", {})['Authorization'] = auth

        # warning: this only works with txrequests! not treq
        for arg in ['cert', 'verify']:
            if arg in config:
                kwargs[arg] = config[arg]

        return kwargs

    @defer.inlineCallbacks
    def _raise_decode_failure_error(self, res: IHttpResponse) -> InlineCallbacksType[None]:
        content = yield res.content()
        msg = "Failed to decode: " + content.decode("utf-8", errors="ignore")[0:200]
        raise KubeTextError(res.code, msg)

    @defer.inlineCallbacks
    def _create_pod(
        self, namespace: str, spec: dict[str, Any]
    ) -> InlineCallbacksType[dict[str, Any]]:
        url = f'/api/v1/namespaces/{namespace}/pods'
        res = yield self._http.post(url, json=spec, **(yield self._get_request_kwargs()))

        try:
            res_json = yield res.json()
        except Exception:
            yield self._raise_decode_failure_error(res)

        if res.code not in (200, 201, 202):
            raise KubeJsonError(res.code, res_json)
        return res_json

    @defer.inlineCallbacks
    def _delete_pod(
        self, namespace: str, name: str, graceperiod: int = 0
    ) -> InlineCallbacksType[dict[str, Any]]:
        url = f'/api/v1/namespaces/{namespace}/pods/{name}'
        res = yield self._http.delete(
            url, params={'graceperiod': graceperiod}, **(yield self._get_request_kwargs())
        )

        try:
            res_json = yield res.json()
        except Exception:
            yield self._raise_decode_failure_error(res)

        if res.code != 200:
            raise KubeJsonError(res.code, res_json)
        return res_json

    @defer.inlineCallbacks
    def _wait_for_pod_deletion(
        self, namespace: str, name: str, timeout: int
    ) -> InlineCallbacksType[None]:
        t1 = self.master.reactor.seconds()
        url = f'/api/v1/namespaces/{namespace}/pods/{name}/status'
        while True:
            if self.master.reactor.seconds() - t1 > timeout:
                raise TimeoutError(f"Did not see pod {name} terminate after {timeout}s")
            res = yield self._http.get(url, **(yield self._get_request_kwargs()))

            try:
                res_json = yield res.json()
            except Exception:
                yield self._raise_decode_failure_error(res)

            if res.code == 404:
                break  # 404 means the pod has terminated
            if res.code != 200:
                raise KubeJsonError(res.code, res_json)
            yield asyncSleep(1, reactor=self.master.reactor)
        return res_json
