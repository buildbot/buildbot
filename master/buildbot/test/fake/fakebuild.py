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

import mock
import posixpath
from twisted.python import components
from buildbot.process import properties
from buildbot import interfaces
from zope.interface import implements

class FakeBuildStatus(properties.PropertiesMixin, mock.Mock):

    # work around http://code.google.com/p/mock/issues/detail?id=105
    def _get_child_mock(self, **kw):
        return mock.Mock(**kw)

    def getInterestedUsers(self):
        return []

components.registerAdapter(
        lambda build_status : build_status.properties,
        FakeBuildStatus, interfaces.IProperties)


class FakeBuild(properties.PropertiesMixin):

    def __init__(self, props=None, buildrequests=[]):
        self.build_status = FakeBuildStatus()
        self.builder = mock.Mock(name='build.builder')
        self.slavebuilder = mock.Mock(name='build.slavebuilder')
        self.path_module = posixpath
        pr = self.build_status.properties = properties.Properties()
        pr.build = self
        self.requests = buildrequests

        self.sources = {}
        if props is None:
            props = properties.Properties()
        props.build = self
        self.build_status.properties = props

    def getSourceStamp(self, codebase):
        if codebase in self.sources:
            return self.sources[codebase]
        return None

    def allStepsDone(self):
        return True


components.registerAdapter(
        lambda build : build.build_status.properties,
        FakeBuild, interfaces.IProperties)

class FakeStepFactory(object):
    """Fake step factory that just returns a fixed step object."""
    implements(interfaces.IBuildStepFactory)
    def __init__(self, step):
        self.step = step

    def buildStep(self):
        return self.step
