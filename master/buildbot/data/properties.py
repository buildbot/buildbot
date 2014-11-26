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

from buildbot.data import base
from buildbot.data import types


class BuildsetPropertiesEndpoint(base.Endpoint):

    isCollection = False
    pathPatterns = """
        /buildsets/n:bsid/properties
    """

    def get(self, resultSpec, kwargs):
        return self.master.db.buildsets.getBuildsetProperties(kwargs['bsid'])


class BuildPropertiesEndpoint(base.Endpoint):

    isCollection = False
    pathPatterns = """
        /builds/n:buildid/properties
    """

    def get(self, resultSpec, kwargs):
        return self.master.db.builds.getBuildProperties(kwargs['buildid'])


class Properties(base.ResourceType):

    name = "property"
    plural = "properties"
    endpoints = [BuildsetPropertiesEndpoint, BuildPropertiesEndpoint]
    keyFields = []

    entityType = types.SourcedProperties()

    @base.updateMethod
    def setBuildProperty(self, buildid, name, value, source):
        return self.master.db.builds.setBuildProperty(
            buildid, name, value, source)
