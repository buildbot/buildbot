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

    def generateUpdateEvent(self, buildid, newprops):
        # This event cannot use the produceEvent mecanism, as the properties resource type is a bit specific
        # (this is a dictionary collection)
        # We only send the new properties, and count on the client to merge the resulting properties dict
        # We are good, as there is no way to delete a property.
        routingKey = ('builds', str(buildid), "properties", "update")
        newprops = self.sanitizeMessage(newprops)
        return self.master.mq.produce(routingKey, newprops)

    @base.updateMethod
    @defer.inlineCallbacks
    def setBuildProperties(self, buildid, properties):
        to_update = {}
        oldproperties = yield self.master.data.get(('builds', str(buildid), "properties"))
        for k, v in properties.getProperties().asDict().iteritems():
            if k in oldproperties and oldproperties[k] == v:
                continue
            to_update[k] = v

        if to_update:
            for k, v in to_update.iteritems():
                yield self.master.db.builds.setBuildProperty(
                    buildid, k, v[0], v[1])
            yield self.generateUpdateEvent(buildid, to_update)

    @base.updateMethod
    @defer.inlineCallbacks
    def setBuildProperty(self, buildid, name, value, source):
        res = yield self.master.db.builds.setBuildProperty(
            buildid, name, value, source)
        yield self.generateUpdateEvent(buildid, dict(name=(value, source)))
        defer.returnValue(res)
