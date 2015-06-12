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
from buildbot.statistics import stats_service


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
