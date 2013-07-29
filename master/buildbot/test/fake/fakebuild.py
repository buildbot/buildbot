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

from buildbot import interfaces
from buildbot.process import properties
from buildbot.status.results import SUCCESS
from twisted.python import components
import mock
import posixpath

class FakeBuildStatus(properties.PropertiesMixin, mock.Mock):

    BuildNumberCounter = 0

    def __init__(self, *args, **kwargs):
        mock.Mock.__init__(self, *args, **kwargs)

        self.BuildNumberCounter += 1

        self.buildNumber = self.BuildNumberCounter
        self.previousBuild = FakeBuildStatus()

    # work around http://code.google.com/p/mock/issues/detail?id=105
    def _get_child_mock(self, **kw):
        return mock.Mock(**kw)

    def getInterestedUsers(self):
        return []

    def getName(self):
        return "fakebuild"

    def getNumber(self):
        return self.buildNumber

    def getText(self):
        return "getText() called"

    def getResults(self):
        return SUCCESS

    def getPreviousBuild(self):
        self.previousBuild

components.registerAdapter(
        lambda build_status : build_status.properties,
        FakeBuildStatus, interfaces.IProperties)


class FakeBuild(properties.PropertiesMixin):

    def __init__(self, props=None):
        self.build_status = FakeBuildStatus()
        self.builder = mock.Mock(name='build.builder')
        self.path_module = posixpath

        self.sources = {}
        if props is None:
            props = properties.Properties()
        props.build = self
        self.build_status.properties = props

    def getSourceStamp(self, codebase):
        if codebase in self.sources:
            return self.sources[codebase]
        return None


components.registerAdapter(
        lambda build : build.build_status.properties,
        FakeBuild, interfaces.IProperties)
