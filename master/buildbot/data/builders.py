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


class BuilderEndpoint(base.BuildNestingMixin, base.Endpoint):

    kind = base.EndpointKind.SINGLE
    pathPatterns = """
        /builders/n:builderid
        /builders/i:buildername
        /masters/n:masterid/builders/n:builderid
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        builderid = yield self.getBuilderId(kwargs)
        if builderid is None:
            return None

        bdict = yield self.master.db.builders.getBuilder(builderid)
        if not bdict:
            return None
        if 'masterid' in kwargs:
            if kwargs['masterid'] not in bdict['masterids']:
                return None
        return {
            "builderid": builderid,
            "name": bdict['name'],
            "masterids": bdict['masterids'],
            "description": bdict['description'],
            "description_format": bdict["description_format"],
            "description_html": bdict["description_html"],
            "projectid": bdict['projectid'],
            "tags": bdict['tags']
        }


class BuildersEndpoint(base.Endpoint):

    kind = base.EndpointKind.COLLECTION
    rootLinkName = 'builders'
    pathPatterns = """
        /builders
        /masters/n:masterid/builders
        /projects/n:projectid/builders
    """

    @defer.inlineCallbacks
    def get(self, resultSpec, kwargs):
        bdicts = yield self.master.db.builders.getBuilders(
            masterid=kwargs.get('masterid', None),
            projectid=kwargs.get('projectid', None)
        )
        return [
            {
                "builderid": bd['id'],
                "name": bd['name'],
                "masterids": bd['masterids'],
                "description": bd['description'],
                "description_format": bd['description_format'],
                "description_html": bd['description_html'],
                "projectid": bd['projectid'],
                "tags": bd['tags']
            }
            for bd in bdicts
        ]

    def get_kwargs_from_graphql(self, parent, resolve_info, args):
        if parent is not None:
            return {'masterid': parent['masterid']}
        return {}


class Builder(base.ResourceType):

    name = "builder"
    plural = "builders"
    endpoints = [BuilderEndpoint, BuildersEndpoint]
    keyField = 'builderid'
    eventPathPatterns = """
        /builders/:builderid
    """
    subresources = ["Build", "Forcescheduler", "Scheduler", "Buildrequest"]

    class EntityType(types.Entity):
        builderid = types.Integer()
        name = types.Identifier(70)
        masterids = types.List(of=types.Integer())
        description = types.NoneOk(types.String())
        description_format = types.NoneOk(types.String())
        description_html = types.NoneOk(types.String())
        projectid = types.NoneOk(types.Integer())
        tags = types.List(of=types.String())
    entityType = EntityType(name, 'Builder')

    @defer.inlineCallbacks
    def generateEvent(self, _id, event):
        builder = yield self.master.data.get(('builders', str(_id)))
        self.produceEvent(builder, event)

    @base.updateMethod
    def findBuilderId(self, name):
        return self.master.db.builders.findBuilderId(name)

    @base.updateMethod
    @defer.inlineCallbacks
    def updateBuilderInfo(self, builderid, description, description_format, description_html,
                          projectid, tags):
        ret = yield self.master.db.builders.updateBuilderInfo(
            builderid, description, description_format, description_html, projectid, tags
        )
        yield self.generateEvent(builderid, "update")
        return ret

    @base.updateMethod
    @defer.inlineCallbacks
    def updateBuilderList(self, masterid, builderNames):
        # get the "current" list of builders for this master, so we know what
        # changes to make.  Race conditions here aren't a great worry, as this
        # is the only master inserting or deleting these records.
        builders = yield self.master.db.builders.getBuilders(masterid=masterid)

        # figure out what to remove and remove it
        builderNames_set = set(builderNames)
        for bldr in builders:
            if bldr['name'] not in builderNames_set:
                builderid = bldr['id']
                yield self.master.db.builders.removeBuilderMaster(
                    masterid=masterid, builderid=builderid)
                self.master.mq.produce(('builders', str(builderid), 'stopped'), {
                    "builderid": builderid,
                    "masterid": masterid,
                    "name": bldr['name']
                })
            else:
                builderNames_set.remove(bldr['name'])

        # now whatever's left in builderNames_set is new
        for name in builderNames_set:
            builderid = yield self.master.db.builders.findBuilderId(name)
            yield self.master.db.builders.addBuilderMaster(
                masterid=masterid, builderid=builderid)
            self.master.mq.produce(('builders', str(builderid), 'started'),
                                   {"builderid": builderid, "masterid": masterid, "name": name})

    # returns a Deferred that returns None
    def _masterDeactivated(self, masterid):
        # called from the masters rtype to indicate that the given master is
        # deactivated
        return self.updateBuilderList(masterid, [])
