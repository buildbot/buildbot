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

from buildbot.data import base
from buildbot.data import types


class Db2DataMixin:

    def db2data(self, dbdict):
        data = {
            'buildid': dbdict['buildid'],
            'name': dbdict['name'],
            'value': dbdict['value'],
            'length': dbdict['length'],
            'source': dbdict['source'],
        }
        return defer.succeed(data)


class BuildDatasNoValueEndpoint(Db2DataMixin, base.BuildNestingMixin, base.Endpoint):

    isCollection = True
    pathPatterns = """
        /builders/n:builderid/builds/n:build_number/data
        /builders/i:buildername/builds/n:build_number/data
        /builds/n:buildid/data
        """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        buildid = yield self.getBuildid(kwargs)

        build_datadicts = yield self.master.db.build_data.getAllBuildDataNoValues(buildid)

        results = []
        for dbdict in build_datadicts:
            results.append((yield self.db2data(dbdict)))
        return results


class BuildDataNoValueEndpoint(Db2DataMixin, base.BuildNestingMixin, base.Endpoint):

    isCollection = False
    pathPatterns = """
        /builders/n:builderid/builds/n:build_number/data/i:name
        /builders/i:buildername/builds/n:build_number/data/i:name
        /builds/n:buildid/data/i:name
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        buildid = yield self.getBuildid(kwargs)
        name = kwargs['name']

        build_datadict = yield self.master.db.build_data.getBuildDataNoValue(buildid, name)

        return (yield self.db2data(build_datadict)) if build_datadict else None


class BuildDataEndpoint(base.BuildNestingMixin, base.Endpoint):

    isCollection = False
    isRaw = True
    pathPatterns = """
        /builders/n:builderid/builds/n:build_number/data/i:name/value
        /builders/i:buildername/builds/n:build_number/data/i:name/value
        /builds/n:buildid/data/i:name/value
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        buildid = yield self.getBuildid(kwargs)
        name = kwargs['name']

        dbdict = yield self.master.db.build_data.getBuildData(buildid, name)
        if not dbdict:
            return None

        return {'raw': dbdict['value'],
                'mime-type': 'application/octet-stream',
                'filename': dbdict['name']}


class BuildData(base.ResourceType):

    name = "build_data"
    plural = "build_data"
    endpoints = [BuildDatasNoValueEndpoint, BuildDataNoValueEndpoint, BuildDataEndpoint]
    keyField = "name"

    class EntityType(types.Entity):
        buildid = types.Integer()
        name = types.String()
        length = types.Integer()
        value = types.NoneOk(types.Binary())
        source = types.String()
    entityType = EntityType(name, 'BuildData')

    @base.updateMethod
    def setBuildData(self, buildid, name, value, source):
        # forward deferred directly
        return self.master.db.build_data.setBuildData(buildid, name, value, source)
