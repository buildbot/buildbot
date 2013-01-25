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

class FakeBuildStatus(properties.PropertiesMixin, mock.Mock):

    # work around http://code.google.com/p/mock/issues/detail?id=105
    def _get_child_mock(self, **kw):
        return mock.Mock(**kw)

    def getInterestedUsers(self):
        return []

components.registerAdapter(
        lambda build_status : build_status.properties,
        FakeBuildStatus, interfaces.IProperties)


class FakeBuild(mock.Mock, properties.PropertiesMixin):

    def __init__(self, *args, **kwargs):
        mock.Mock.__init__(self, *args, **kwargs)
        self.build_status = FakeBuildStatus()
        self.path_module = posixpath
        pr = self.build_status.properties = properties.Properties()
        pr.build = self

    # work around http://code.google.com/p/mock/issues/detail?id=105
    def _get_child_mock(self, **kw):
        return mock.Mock(**kw)

components.registerAdapter(
        lambda build : build.build_status.properties,
        FakeBuild, interfaces.IProperties)
