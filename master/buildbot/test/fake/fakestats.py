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

from __future__ import annotations

from typing import Any

from buildbot.process import buildstep
from buildbot.process.results import SUCCESS
from buildbot.statistics import capture
from buildbot.statistics.storage_backends.base import StatsStorageBase


class FakeStatsStorageService(StatsStorageBase):
    """
    Fake Storage service used in unit tests
    """

    def __init__(
        self,
        stats: list[capture.Capture] | None = None,
        name: str = 'FakeStatsStorageService',
    ) -> None:
        self.stored_data: list[tuple[dict[str, Any], str, dict[str, str]]] = []
        if not stats:
            self.stats: list[capture.Capture] = [capture.CaptureProperty("TestBuilder", 'test')]
        else:
            self.stats = stats
        self.name = name
        self.captures: list[capture.Capture] = []

    def thd_postStatsValue(
        self,
        post_data: dict[str, Any],
        series_name: str,
        context: dict[str, str] | None = None,
    ) -> None:
        if not context:
            context = {}
        self.stored_data.append((post_data, series_name, context))


class FakeBuildStep(buildstep.BuildStep):
    """
    A fake build step to be used for testing.
    """

    def doSomething(self) -> None:
        self.setProperty("test", 10, "test")

    def start(self) -> int:
        self.doSomething()
        return SUCCESS


class FakeInfluxDBClient:
    """
    Fake Influx module for testing on systems that don't have influxdb installed.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.points: list[dict[str, Any]] = []

    def write_points(self, points: list[dict[str, Any]]) -> None:
        self.points.extend(points)
