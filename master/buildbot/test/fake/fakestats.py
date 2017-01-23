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

from buildbot.process import buildstep
from buildbot.process.results import SUCCESS
from buildbot.statistics import capture
from buildbot.statistics import stats_service
from buildbot.statistics.storage_backends.base import StatsStorageBase


class FakeStatsStorageService(StatsStorageBase):

    """
    Fake Storage service used in unit tests
    """

    def __init__(self, stats=None, name='FakeStatsStorageService'):
        self.stored_data = []
        if not stats:
            self.stats = [capture.CaptureProperty("TestBuilder",
                                                  'test')]
        else:
            self.stats = stats
        self.name = name
        self.captures = []

    @defer.inlineCallbacks
    def thd_postStatsValue(self, post_data, series_name, context=None):
        if not context:
            context = {}
        self.stored_data.append((post_data, series_name, context))
        yield defer.succeed(None)


class FakeBuildStep(buildstep.BuildStep):

    """
    A fake build step to be used for testing.
    """

    def doSomething(self):
        self.setProperty("test", 10, "test")

    def start(self):
        self.doSomething()
        return SUCCESS


class FakeStatsService(stats_service.StatsService):

    """
    Fake StatsService for use in fakemaster
    """

    def __init__(self, master=None, *args, **kwargs):
        stats_service.StatsService.__init__(self, *args, **kwargs)
        self.master = master

    @property
    def master(self):
        return self._master

    @master.setter
    def master(self, value):
        self._master = value


class FakeInfluxDBClient(object):

    """
    Fake Influx module for testing on systems that don't have influxdb installed.
    """

    def __init__(self, *args, **kwargs):
        self.points = []

    def write_points(self, points):
        self.points.extend(points)
