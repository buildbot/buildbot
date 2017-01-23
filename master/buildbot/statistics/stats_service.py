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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer
from twisted.python import log

from buildbot.statistics.storage_backends.base import StatsStorageBase
from buildbot.util import service


class StatsService(service.BuildbotService):

    """
    A middleware for passing on statistics data to all storage backends.
    """

    def checkConfig(self, storage_backends):
        for wfb in storage_backends:
            if not isinstance(wfb, StatsStorageBase):
                raise TypeError("Invalid type of stats storage service {0!r}. "
                                "Should be of type StatsStorageBase, "
                                "is: {0!r}".format(type(StatsStorageBase)))

    def reconfigService(self, storage_backends):
        log.msg(
            "Reconfiguring StatsService with config: {0!r}".format(storage_backends))

        self.checkConfig(storage_backends)

        self.registeredStorageServices = []
        for svc in storage_backends:
            self.registeredStorageServices.append(svc)

        self.consumers = []
        self.registerConsumers()

    @defer.inlineCallbacks
    def registerConsumers(self):
        self.removeConsumers()  # remove existing consumers and add new ones
        self.consumers = []

        for svc in self.registeredStorageServices:
            for cap in svc.captures:
                cap.parent_svcs.append(svc)
                cap.master = self.master
                consumer = yield self.master.mq.startConsuming(cap.consume, cap.routingKey)
                self.consumers.append(consumer)

    @defer.inlineCallbacks
    def stopService(self):
        yield service.BuildbotService.stopService(self)
        self.removeConsumers()

    @defer.inlineCallbacks
    def removeConsumers(self):
        for consumer in self.consumers:
            yield consumer.stopConsuming()
        self.consumers = []

    @defer.inlineCallbacks
    def yieldMetricsValue(self, data_name, post_data, buildid):
        """
        A method to allow posting data that is not generated and stored as build-data in
        the database. This method generates the `stats-yield-data` event to the mq layer
        which is then consumed in self.postData.

        @params
        data_name: (str) The unique name for identifying this data.
        post_data: (dict) A dictionary of key-value pairs that'll be sent for storage.
        buildid: The buildid of the current Build.
        """
        build_data = yield self.master.data.get(('builds', buildid))
        routingKey = ("stats-yieldMetricsValue", "stats-yield-data")

        msg = {
            'data_name': data_name,
            'post_data': post_data,
            'build_data': build_data
        }

        self.master.mq.produce(routingKey, msg)
