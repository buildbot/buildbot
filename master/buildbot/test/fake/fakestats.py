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


from buildbot.process import buildstep
from buildbot.process.results import SUCCESS
from buildbot.statistics import capture
from buildbot.statistics.storage_backends.base import StatsStorageBase


class FakeStatsStorageService(StatsStorageBase):

    """
    Fake Storage service used in unit tests
    """

    def __init__(self, stats=None, name="FakeStatsStorageService"):
        self.stored_data = []
        if not stats:
            self.stats = [capture.CaptureProperty("TestBuilder", "test")]
        else:
            self.stats = stats
        self.name = name
        self.captures = []

    def thd_postStatsValue(self, post_data, series_name, context=None):
        if not context:
            context = {}
        self.stored_data.append((post_data, series_name, context))


class FakeBuildStep(buildstep.BuildStep):

    """
    A fake build step to be used for testing.
    """

    def doSomething(self):
        self.setProperty("test", 10, "test")

    def start(self):
        self.doSomething()
        return SUCCESS


class FakeInfluxDBClient:

    """
    Fake Influx module for testing on systems that don't have influxdb installed.
    """

    def __init__(self, *args, **kwargs):
        self.points = []

    def write_points(self, points):
        self.points.extend(points)
