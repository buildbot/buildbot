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

from twisted.python import log

from buildbot import config
from buildbot.statistics.storage_backends.base import StatsStorageBase

try:
    from influxdb import InfluxDBClient
except ImportError:
    InfluxDBClient = None


class InfluxStorageService(StatsStorageBase):

    """
    Delegates data to InfluxDB
    """

    def __init__(self, url, port, user, password, db, captures,
                 name="InfluxStorageService"):
        if not InfluxDBClient:
            config.error("Python client for InfluxDB not installed.")
            return
        self.url = url
        self.port = port
        self.user = user
        self.password = password
        self.db = db
        self.name = name

        self.captures = captures
        self.client = InfluxDBClient(self.url, self.port, self.user,
                                     self.password, self.db)
        self._inited = True

    def thd_postStatsValue(self, post_data, series_name, context=None):
        if not self._inited:
            log.err(f"Service {self.name} not initialized")
            return

        data = {
            'measurement': series_name,
            'fields': post_data
        }

        log.msg("Sending data to InfluxDB")
        log.msg(f"post_data: {post_data!r}")
        if context:
            log.msg(f"context: {context!r}")
            data['tags'] = context

        self.client.write_points([data])
