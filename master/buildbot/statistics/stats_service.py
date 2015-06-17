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

from twisted.internet import threads
from twisted.python import log

from buildbot.util import service
from buildbot.statistics.storage_backends import StatsStorageBase


class StatsService(service.ReconfigurableServiceMixin, service.AsyncMultiService):
    """
    A middleware for passing on statistics data to all storage backends.
    """
    def __init__(self, master):
        service.AsyncMultiService.__init__(self)
        self.setName('StatsService')
        log.msg("Creating StatsService")
        self.master = master
        self.registeredStorageServices = []

    def reconfigServiceWithBuildbotConfig(self, new_config):
        log.msg("Reconfiguring StatsService with config: {0!r}".format(new_config))

        # To remove earlier used services when reconfig happens
        self.registeredStorageServices = []
        for svc in new_config.statsServices:
            if not isinstance(svc, StatsStorageBase):
                raise TypeError("Invalid type of stats storage service {0!r}. "
                                "Should be of type StatsStorageBase, "
                                "is: {0!r}".format(type(StatsStorageBase)))
            self.registeredStorageServices.append(svc)

        return service.ReconfigurableServiceMixin.reconfigServiceWithBuildbotConfig(self,
                                                                                    new_config)

    def postProperties(self, properties, builder_name):
        """
        Expose all properties set in a step to be filtered and posted to
        statistics storage.
        """
        for svc in self.registeredStorageServices:
            for cap in svc.captures:
                for prop_name in properties.properties:
                    if builder_name == cap.builder_name and \
                       prop_name == cap.property_name:
                        context = {
                            "builder_name": builder_name
                        }
                        series_name = builder_name + "-" + prop_name
                        return threads.deferToThread(svc.postStatsValue, prop_name,
                                                 properties.getProperty(prop_name),
                                                 series_name, context)
