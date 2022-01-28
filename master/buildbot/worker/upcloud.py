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
# -*- Coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import hashlib
import socket

from twisted.internet import defer
from twisted.python import log

from buildbot import config
from buildbot import util
from buildbot.interfaces import LatentWorkerFailedToSubstantiate
from buildbot.util.httpclientservice import HTTPClientService
from buildbot.worker import AbstractLatentWorker

DEFAULT_ZONE = "de-fra1"
DEFAULT_PLAN = "1xCPU-1GB"
DEFAULT_BASE_URL = "https://api.upcloud.com/1.3"

DEFAULT_OS_DISK_SIZE = 10
DEFAULT_CORE_NUMBER = 1
DEFAULT_MEMORY_AMOUNT = 512


class UpcloudLatentWorker(AbstractLatentWorker):
    instance = None

    def checkConfig(self, name, password=None, api_username=None, api_password=None, image=None,
                    hostconfig=None, base_url=DEFAULT_BASE_URL, masterFQDN=None, **kwargs):

        if image is None or api_username is None or api_password is None:
            config.error("UpcloudLatentWorker: You need to specify at least"
                         " an image name, zone, api_username and api_password")

        AbstractLatentWorker.checkConfig(self, name, password, **kwargs)

    @defer.inlineCallbacks
    def reconfigService(self, name, password=None, zone=None, api_username=None, api_password=None,
                        image=None, hostconfig=None, base_url=DEFAULT_BASE_URL, masterFQDN=None,
                        **kwargs):
        if password is None:
            password = self.getRandomPass()
        if masterFQDN is None:
            masterFQDN = socket.getfqdn()
        self.masterFQDN = masterFQDN
        self.image = image
        if hostconfig is None:
            hostconfig = {}
        self.hostconfig = hostconfig
        self.client = yield HTTPClientService.getService(self.master, base_url,
                                                         auth=(api_username, api_password),
                                                         debug=kwargs.get('debug', False))
        masterName = util.unicode2bytes(self.master.name)
        self.masterhash = hashlib.sha1(masterName).hexdigest()[:6]
        yield AbstractLatentWorker.reconfigService(self, name, password, **kwargs)

    @defer.inlineCallbacks
    def _resolve_image(self, image):
        # get templates
        result = yield self.client.get("/storage/template")
        uuid = None
        if result.code == 200:
            templates = yield result.json()
            for template in templates["storages"]["storage"]:
                if image == template["title"]:
                    uuid = template["uuid"]
                    break
        return uuid

    def getContainerName(self):
        return (f'buildbot-{self.workername}-{self.masterhash}').replace("_", "-")

    @defer.inlineCallbacks
    def start_instance(self, build):
        if self.instance is not None:
            raise ValueError('instance active')

        # convert image to UUID
        image, hostconfig = yield build.render([self.image, self.hostconfig])
        image_uuid = yield self._resolve_image(image)

        if image_uuid is None:
            log.msg(f"{self.__class__.__name__} {self.workername}: Instance creation failed: "
                    f"Cannot find template {image}")
            raise LatentWorkerFailedToSubstantiate(self.getContainerName(), 'resolving image')

        # compose json
        req = {
            "server": {
                "zone": hostconfig.get('zone', DEFAULT_ZONE),
                "title": self.getContainerName(),
                "hostname": hostconfig.get('hostname', self.name),
                "user_data": hostconfig.get('user_data', ""),
                "login_user": {
                    "username": "root",
                    "ssh_keys": {
                        "ssh_key": hostconfig.get('ssh_keys', []),
                    },
                },
                "password_delivery": "none",
                "storage_devices": {
                    "storage_device": [{
                        "action": "clone",
                        "storage": image_uuid,
                        "title": self.getContainerName(),
                        "size": hostconfig.get("os_disk_size",
                            DEFAULT_OS_DISK_SIZE),
                        "tier": "maxiops",
                    }],
                }
            }
        }

        req["server"]["plan"] = hostconfig.get("plan", DEFAULT_PLAN)
        if req["server"]["plan"] == "custom":
            req["server"]["core_number"] = hostconfig.get("core_number", DEFAULT_CORE_NUMBER)
            req["server"]["memory_amount"] = hostconfig.get("memory_amount", DEFAULT_MEMORY_AMOUNT)

        # request instance
        result = yield self.client.post("/server", json=req)

        if result.code // 100 != 2:
            reason = yield result.content()
            log.msg(f"{self.__class__.__name__} {self.workername}: Instance creation failed: "
                    f"{result.code} {reason}")
            self.failed_to_start(req['server']['hostname'], 'starting')

        instance = yield result.json()
        self.instance = instance["server"]
        self.instance["Id"] = self.instance["uuid"].split("-")[-1]

        # wait until server is actually up
        while (yield self._state()) not in ["started"]:
            yield util.asyncSleep(1, reactor=self.master.reactor)

        result = yield self.client.get(f'/server/{self.instance["uuid"]}')
        instance = yield result.json()
        log.msg(f'{self.__class__.__name__} {self.workername}: Instance {self.instance["Id"]} '
                f'created (root password {self.instance["password"]})')
        # include root password as worker property
        self.properties.setProperty("root_password", self.instance['password'], "Worker")
        return [self.instance["Id"], image]

    @defer.inlineCallbacks
    def _state(self):
        result = yield self.client.get(f'/server/{self.instance["uuid"]}')
        if result.code == 404:
            return "absent"
        else:
            server = yield result.json()
            return server["server"]["state"]

    @defer.inlineCallbacks
    def stop_instance(self, fast=False):
        if self.instance is None:
            # be gentle. Something may just be trying to alert us that an
            # instance never attached, and it's because, somehow, we never
            # started.
            return
        log.msg(f'{self.__class__.__name__} {self.workername}: Stopping instance '
                f'{self.instance["Id"]}...')
        result = yield self.client.post(f'/server/{self.instance["uuid"]}/stop', json={
            "stop_server": {
                "stop_type": "hard",
                "timeout": "1"
            }}
        )
        if result.code // 100 != 2:
            reason = yield result.content()
            reason = (f'{self.__class__.__name__} {self.workername} failed to stop instance '
                      f'{self.instance["Id"]} ({self._state()}): {reason.decode()}')
            self.instance = None
            raise Exception(reason)
        while (yield self._state()) not in ["stopped", "absent"]:
            yield util.asyncSleep(1, reactor=self.master.reactor)

        # destroy it
        result = yield self.client.delete(f'/server/{self.instance["uuid"]}?storages=1')
        if result.code // 100 != 2:
            reason = yield result.content()
            reason = (f'{self.__class__.__name__} {self.workername} failed to delete instance '
                      f'{self.instance["Id"]} ({self._state()}): {reason.decode()}')
            self.instance = None
            raise Exception(reason)
