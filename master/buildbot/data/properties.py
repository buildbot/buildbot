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

import json
from typing import TYPE_CHECKING
from typing import Any

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import types

if TYPE_CHECKING:
    from buildbot.interfaces import IProperties
    from buildbot.util.twisted import InlineCallbacksType


class BuildsetPropertiesEndpoint(base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/buildsets/n:bsid/properties",
    ]

    def get(self, resultSpec, kwargs):
        return self.master.db.buildsets.getBuildsetProperties(kwargs['bsid'])


class BuildPropertiesEndpoint(base.Endpoint):
    kind = base.EndpointKind.SINGLE
    pathPatterns = [
        "/builders/n:builderid/builds/n:build_number/properties",
        "/builds/n:buildid/properties",
    ]

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        retriever = base.NestedBuildDataRetriever(self.master, kwargs)
        buildid = yield retriever.get_build_id()
        build_properties = yield self.master.db.builds.getBuildProperties(buildid)
        return build_properties


class PropertiesListEndpoint(base.Endpoint):
    kind = base.EndpointKind.COLLECTION
    pathPatterns = [
        "/builds/n:buildid/property_list",
        "/buildsets/n:bsid/properties_list",
        "/changes/n:changeid/properties_list",
    ]
    buildFieldMapping = {
        "name": "build_properties.name",
        "source": "build_properties.source",
        "value": "build_properties.value",
    }
    buildsetFieldMapping = {
        "name": "buildset_properties.name",
        "source": "buildset_properties.source",
        "value": "buildset_properties.value",
    }
    changeFieldMapping = {
        "name": "change_properties.name",
        "source": "change_properties.source",
        "value": "change_properties.value",
    }

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        buildid = kwargs.get("buildid", None)
        bsid = kwargs.get("bsid", None)
        changeid = kwargs.get("changeid", None)
        if buildid is not None:
            if resultSpec is not None:
                resultSpec.fieldMapping = self.buildFieldMapping
            props = yield self.master.db.builds.getBuildProperties(buildid, resultSpec)
        elif bsid is not None:
            if resultSpec is not None:
                resultSpec.fieldMapping = self.buildsetFieldMapping
            props = yield self.master.db.buildsets.getBuildsetProperties(bsid)
        elif changeid is not None:
            if resultSpec is not None:
                resultSpec.fieldMapping = self.buildsetFieldMapping
            props = yield self.master.db.changes.getChangeProperties(changeid)
        return [{'name': k, 'source': v[1], 'value': json.dumps(v[0])} for k, v in props.items()]


class Property(base.ResourceType):
    name = "_property"
    plural = "_properties"
    endpoints = [PropertiesListEndpoint]

    entityType = types.PropertyEntityType(name)


class Properties(base.ResourceType):
    name = "property"
    plural = "properties"
    endpoints = [BuildsetPropertiesEndpoint, BuildPropertiesEndpoint]

    entityType = types.SourcedProperties()

    def generateUpdateEvent(self, buildid, newprops):
        # This event cannot use the produceEvent mechanism, as the properties resource type is a bit
        # specific (this is a dictionary collection)
        # We only send the new properties, and count on the client to merge the resulting properties
        # dict
        # We are good, as there is no way to delete a property.
        routingKey = ('builds', str(buildid), "properties", "update")
        newprops = self.sanitizeMessage(newprops)
        return self.master.mq.produce(routingKey, newprops)

    @base.updateMethod
    @defer.inlineCallbacks
    def setBuildProperties(
        self, buildid: int, properties: IProperties
    ) -> InlineCallbacksType[None]:
        to_update = {}
        oldproperties = yield self.master.data.get(('builds', str(buildid), "properties"))
        properties_real = properties.getProperties()
        properties_dict = yield properties_real.render(properties_real.asDict())
        for k, v in properties_dict.items():
            if k in oldproperties and oldproperties[k] == v:
                continue
            to_update[k] = v

        if to_update:
            for k, v in to_update.items():
                yield self.master.db.builds.setBuildProperty(buildid, k, v[0], v[1])
            yield self.generateUpdateEvent(buildid, to_update)

    @base.updateMethod
    @defer.inlineCallbacks
    def setBuildProperty(
        self, buildid: int, name: str, value: Any, source: str
    ) -> InlineCallbacksType[None]:
        res = yield self.master.db.builds.setBuildProperty(buildid, name, value, source)
        yield self.generateUpdateEvent(buildid, {"name": (value, source)})
        return res
