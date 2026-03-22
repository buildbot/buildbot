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

import posixpath
from pathlib import PurePosixPath
from typing import Any
from unittest import mock

from buildbot import config
from buildbot.process import factory
from buildbot.process import properties
from buildbot.process import workerforbuilder
from buildbot.test.fake import fakemaster
from buildbot.worker import base


class FakeWorkerStatus(properties.PropertiesMixin):
    def __init__(self, name: str) -> None:
        self.name = name
        self.info = properties.Properties()
        self.info.setProperty("test", "test", "Worker")


class FakeBuildRequest:
    def __init__(self) -> None:
        self.priority = 0


class FakeBuild(properties.PropertiesMixin):
    def __init__(self, props: properties.Properties | None = None, master: Any = None) -> None:
        self.builder = fakemaster.FakeBuilder(master)
        self.workerforbuilder = mock.Mock(spec=workerforbuilder.WorkerForBuilder)
        self.workerforbuilder.worker = mock.Mock(spec=base.Worker)
        self.workerforbuilder.worker.info = properties.Properties()
        self.workerforbuilder.worker.workername = 'workername'
        self.builder.config = config.BuilderConfig(  # type: ignore[attr-defined]
            name='bldr', workernames=['a'], factory=factory.BuildFactory()
        )
        self.path_module = posixpath
        self.path_cls = PurePosixPath
        self.buildid = 92
        self.number = 13
        self.workdir = 'build'
        self.locks: list[Any] = []
        self._locks_to_acquire: list[Any] = []

        self.sources: dict[str, Any] = {}
        if props is None:
            props = properties.Properties()
        props.build = self
        self.properties = props
        self.master = None
        self.config_version = 0
        self.requests = [FakeBuildRequest()]
        self.env: dict[str, str] = {}

    def getProperties(self) -> properties.Properties:
        return self.properties

    def getSourceStamp(self, codebase: str) -> Any:
        if codebase in self.sources:
            return self.sources[codebase]
        return None

    def getAllSourceStamps(self) -> list[Any]:
        return list(self.sources.values())

    def allChanges(self) -> Any:
        for s in self.sources.values():
            yield from s.changes

    def allFiles(self) -> list[str]:
        files = []
        for c in self.allChanges():
            for f in c.files:
                files.append(f)
        return files

    def getBuilder(self) -> fakemaster.FakeBuilder:
        return self.builder

    def getWorkerInfo(self) -> properties.Properties:
        return self.workerforbuilder.worker.info

    def setUniqueStepName(self, name: str) -> str:
        return name


class FakeBuildForRendering:
    def render(self, r: Any) -> Any:
        if isinstance(r, str):
            return "rendered:" + r
        if isinstance(r, list):
            return list(self.render(i) for i in r)
        if isinstance(r, tuple):
            return tuple(self.render(i) for i in r)
        return r
