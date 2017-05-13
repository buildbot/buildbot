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

import posixpath

import mock

from twisted.python import components

from buildbot import config
from buildbot import interfaces
from buildbot.process import factory
from buildbot.process import properties
from buildbot.process import workerforbuilder
from buildbot.test.fake import fakemaster
from buildbot.worker import base


class FakeBuildStatus(properties.PropertiesMixin, object):

    def __init__(self):
        self.properties = properties.Properties()

    def getInterestedUsers(self):
        return []

    def setWorkername(self, _):
        pass

    def setSourceStamps(self, _):
        pass

    def setReason(self, _):
        pass

    def setBlamelist(self, _):
        pass

    def buildStarted(self, _):
        return True

    setText = mock.Mock()
    setText2 = mock.Mock()
    setResults = mock.Mock()

    def buildFinished(self):
        pass

    getBuilder = mock.Mock()


components.registerAdapter(
    lambda build_status: build_status.properties,
    FakeBuildStatus, interfaces.IProperties)


class FakeBuild(properties.PropertiesMixin):

    def __init__(self, props=None, master=None):
        self.build_status = FakeBuildStatus()
        self.builder = fakemaster.FakeBuilderStatus(master)
        self.workerforbuilder = mock.Mock(
            spec=workerforbuilder.WorkerForBuilder)
        self.workerforbuilder.worker = mock.Mock(spec=base.Worker)
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
        self.build_status.properties = props
        self.properties = props

    def getSourceStamp(self, codebase):
        if codebase in self.sources:
            return self.sources[codebase]
        return None

    def allFiles(self):
        return []

    def getBuilder(self):
        return self.builder


components.registerAdapter(
    lambda build: build.build_status.properties,
    FakeBuild, interfaces.IProperties)
