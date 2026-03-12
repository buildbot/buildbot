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

from buildbot import util
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.util.httpclientservice import HTTPSession
from buildbot.util.latent import CompatibleLatentWorkerMixin
from buildbot.worker.docker import DockerBaseWorker

if TYPE_CHECKING:
    from buildbot.process.build import Build
    from buildbot.util.twisted import InlineCallbacksType

log = Logger()


class MarathonLatentWorker(CompatibleLatentWorkerMixin, DockerBaseWorker):
    """Marathon is a distributed docker container launcher for Mesos"""

    instance = None
    image = None
    _http = None

    def checkConfig(  # type: ignore[override]
        self,
        name: str,
        marathon_url: str,
        image: str,
        marathon_auth: tuple[str, str] | None = None,
        marathon_extra_config: dict[str, Any] | None = None,
        marathon_app_prefix: str = "buildbot-worker/",
        masterFQDN: str | None = None,
        **kwargs: Any,
    ) -> None:
        super().checkConfig(name, image=image, masterFQDN=masterFQDN, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(  # type: ignore[override]
        self,
        name: str,
        marathon_url: str,
        image: str,
        marathon_auth: tuple[str, str] | None = None,
        marathon_extra_config: dict[str, Any] | None = None,
        marathon_app_prefix: str = "buildbot-worker/",
        masterFQDN: str | None = None,
        **kwargs: Any,
    ) -> InlineCallbacksType[None]:
        # Set build_wait_timeout to 0s if not explicitly set: Starting a
        # container is almost immediate, we can afford doing so for each build.

        if 'build_wait_timeout' not in kwargs:
            kwargs['build_wait_timeout'] = 0
        yield super().reconfigService(name, image=image, masterFQDN=masterFQDN, **kwargs)

        self._http = HTTPSession(self.master.httpservice, marathon_url, auth=marathon_auth)
        if marathon_extra_config is None:
            marathon_extra_config = {}
        self.marathon_extra_config = marathon_extra_config
        self.marathon_app_prefix = marathon_app_prefix

    def getApplicationId(self) -> str:
        return self.marathon_app_prefix + self.getContainerName()

    def renderWorkerProps(self, build: Build) -> defer.Deferred[Any]:  # type: ignore[override]
        return build.render((self.image, self.marathon_extra_config))

    @defer.inlineCallbacks
    def start_instance(self, build: Build) -> InlineCallbacksType[bool]:
        yield self.stop_instance(reportFailure=False)

        image, marathon_extra_config = yield self.renderWorkerPropsOnStart(build)  # type: ignore[arg-type]

        marathon_config = {
            "container": {
                "docker": {
                    "image": image,
                    "network": "BRIDGE",
                },
                "type": "DOCKER",
            },
            "id": self.getApplicationId(),
            "instances": 1,
            "env": self.createEnvironment(),
        }
        util.dictionary_merge(marathon_config, marathon_extra_config)
        res = yield self._http.post("/v2/apps", json=marathon_config)  # type: ignore[union-attr]
        res_json = yield res.json()
        if res.code != 201:
            raise LatentWorkerFailedToSubstantiate(
                f"Unable to create Marathon app: {self.getApplicationId()} "
                f"{res.code}: {res_json['message']} {res_json}"
            )
        self.instance = res_json
        return True

    @defer.inlineCallbacks
    def stop_instance(  # type: ignore[override]
        self, fast: bool = False, reportFailure: bool = True
    ) -> InlineCallbacksType[None]:
        res = yield self._http.delete(f"/v2/apps/{self.getApplicationId()}")  # type: ignore[union-attr]
        self.instance = None
        self.resetWorkerPropsOnStop()

        if res.code != 200 and reportFailure:
            res_json = yield res.json()
            # the error is not documented :-(
            log.warn(
                "Unable to delete Marathon app: {id} {code}: {message} {details}",
                id=self.getApplicationId(),
                code=res.code,
                message=res_json.get('message'),
                details=res_json,
            )
