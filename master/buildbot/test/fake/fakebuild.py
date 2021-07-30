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

import posixpath

import mock

from buildbot import config
from buildbot.process import factory
from buildbot.process import properties
from buildbot.process import workerforbuilder
from buildbot.test.fake import fakemaster
from buildbot.worker import base


class FakeWorkerStatus(properties.PropertiesMixin):

    def __init__(self, name):
        self.name = name
        self.info = properties.Properties()
        self.info.setProperty("test", "test", "Worker")


class FakeBuild(properties.PropertiesMixin):

    def __init__(self, props=None, master=None):
        self.builder = fakemaster.FakeBuilder(master)
        self.workerforbuilder = mock.Mock(
            spec=workerforbuilder.WorkerForBuilder)
        self.workerforbuilder.worker = mock.Mock(spec=base.Worker)
        self.workerforbuilder.worker.info = properties.Properties()
        self.workerforbuilder.worker.workername = 'workername'
        self.builder.config = config.BuilderConfig(
            name='bldr',
            workernames=['a'],
            factory=factory.BuildFactory())
        self.path_module = posixpath
        self.buildid = 92
        self.number = 13
        self.workdir = 'build'
        self.locks = []

        self.sources = {}
        if props is None:
            props = properties.Properties()
        props.build = self
        self.properties = props
        self.master = None
        self.config_version = 0

    def getProperties(self):
        return self.properties

    def getSourceStamp(self, codebase):
        if codebase in self.sources:
            return self.sources[codebase]
        return None

    def getAllSourceStamps(self):
        return list(self.sources.values())

    def allChanges(self):
        for s in self.sources.values():
            for c in s.changes:
                yield c

    def allFiles(self):
        files = []
        for c in self.allChanges():
            for f in c.files:
                files.append(f)
        return files

    def getBuilder(self):
        return self.builder

    def getWorkerInfo(self):
        return self.workerforbuilder.worker.info

    def setUniqueStepName(self, step):
        pass


class FakeBuildForRendering:
    def render(self, r):
        if isinstance(r, str):
            return "rendered:" + r
        if isinstance(r, list):
            return list(self.render(i) for i in r)
        if isinstance(r, tuple):
            return tuple(self.render(i) for i in r)
        return r
