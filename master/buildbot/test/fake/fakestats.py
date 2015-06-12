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

from twisted.internet import defer
from buildbot.process import buildstep
from buildbot.statistics import stats_service
from buildbot.statistics import storage_backends
from buildbot.statistics import capture
from buildbot.status.results import SUCCESS


class FakeStatsStorageService(storage_backends.StatsStorageBase):
    """
    Fake Storage service used in unit tests
    """
    def __init__(self, stats=None):
        self.stored_data = []
        if not stats:
            self.stats = [capture.CaptureProperty("TestBuilder",
                                                  'test')]
        else:
            self.stats = stats

    @defer.inlineCallbacks
    def postStatsValue(self, name, value, series_name, context={}):
        self.stored_data.append((name, value, series_name, context))
        yield None


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
    @defer.inlineCallbacks
    def postProperties(self, properties, builder_name):
        """
        No filtering. Straight post stuff to FakeStatsStorageService.
        """
        for svc in self.registeredStorageServices:
            for prop_name in properties.properties:
                context = {
                    "builder_name": builder_name
                }
                series_name = builder_name + "-" + prop_name
                yield svc.postStatsValue(prop_name,
                                         properties.getProperty(prop_name),
                                         series_name, context)
