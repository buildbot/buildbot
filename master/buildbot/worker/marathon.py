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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from twisted.internet import defer

from buildbot import util
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.util.httpclientservice import HTTPClientService
from buildbot.util.logger import Logger
from buildbot.worker.docker import DockerBaseWorker

log = Logger()


class MarathonLatentWorker(DockerBaseWorker):
    """Marathon is a distributed docker container launcher for Mesos"""
    instance = None
    image = None
    _http = None

    def checkConfig(self,
                    name,
                    marathon_url,
                    image,
                    marathon_auth=None,
                    marathon_extra_config=None,
                    marathon_app_prefix="buildbot-worker/",
                    masterFQDN=None,
                    **kwargs):

        DockerBaseWorker.checkConfig(
            self, name, image=image, masterFQDN=masterFQDN, **kwargs)
        HTTPClientService.checkAvailable(self.__class__.__name__)

    @defer.inlineCallbacks
    def reconfigService(self,
                        name,
                        marathon_url,
                        image,
                        marathon_auth=None,
                        marathon_extra_config=None,
                        marathon_app_prefix="buildbot-worker/",
                        masterFQDN=None,
                        **kwargs):

        # Set build_wait_timeout to 0s if not explicitly set: Starting a
        # container is almost immediate, we can afford doing so for each build.

        if 'build_wait_timeout' not in kwargs:
            kwargs['build_wait_timeout'] = 0
        yield DockerBaseWorker.reconfigService(
            self, name, image=image, masterFQDN=masterFQDN, **kwargs)

        self._http = yield HTTPClientService.getService(
            self.master, marathon_url, auth=marathon_auth)
        if marathon_extra_config is None:
            marathon_extra_config = {}
        self.marathon_extra_config = marathon_extra_config
        self.marathon_app_prefix = marathon_app_prefix

    def getApplicationId(self):
        return self.marathon_app_prefix + self.getContainerName()

    @defer.inlineCallbacks
    def start_instance(self, build):
        yield self.stop_instance(reportFailure=False)
        image = yield build.render(self.image)
        marathon_extra_config = yield build.render(self.marathon_extra_config)
        marathon_config = {
            "container": {
                "docker": {
                    "image": image,
                    "network": "BRIDGE",
                },
                "type": "DOCKER"
            },
            "id": self.getApplicationId(),
            "instances": 1,
            "env": self.createEnvironment()
        }
        util.dictionary_merge(marathon_config, marathon_extra_config)
        res = yield self._http.post("/v2/apps", json=marathon_config)
        res_json = yield res.json()
        if res.code != 201:
            raise LatentWorkerFailedToSubstantiate(
                "Unable to create Marathon app: {} {}: {} {}".format(
                    self.getApplicationId(), res.code, res_json['message'],
                    res_json))
        self.instance = res_json
        defer.returnValue(True)

    @defer.inlineCallbacks
    def stop_instance(self, fast=False, reportFailure=True):
        res = yield self._http.delete("/v2/apps/{}".format(
            self.getApplicationId()))
        self.instance = None

        if res.code != 200 and reportFailure:
            res_json = yield res.json()
            # the error is not documented :-(
            log.warn(
                "Unable to delete Marathon app: {id} {code}: {message} {details}",
                id=self.getApplicationId(),
                code=res.code,
                message=res_json.get('message'),
                details=res_json)
