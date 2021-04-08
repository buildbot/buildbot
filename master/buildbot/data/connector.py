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

import functools
import inspect
import textwrap

from twisted.internet import defer
from twisted.python import reflect

from buildbot.data import base
from buildbot.data import exceptions
from buildbot.data import resultspec
from buildbot.data.types import Entity
from buildbot.util import pathmatch
from buildbot.util import service


class Updates:
    # empty container object; see _scanModule, below
    pass


class RTypes:
    # empty container object; see _scanModule, below
    pass


class DataConnector(service.AsyncService):

    submodules = [
        'buildbot.data.build_data',
        'buildbot.data.builders',
        'buildbot.data.builds',
        'buildbot.data.buildrequests',
        'buildbot.data.workers',
        'buildbot.data.steps',
        'buildbot.data.logs',
        'buildbot.data.logchunks',
        'buildbot.data.buildsets',
        'buildbot.data.changes',
        'buildbot.data.changesources',
        'buildbot.data.masters',
        'buildbot.data.sourcestamps',
        'buildbot.data.schedulers',
        'buildbot.data.forceschedulers',
        'buildbot.data.root',
        'buildbot.data.properties',
        'buildbot.data.test_results',
        'buildbot.data.test_result_sets',
    ]
    name = "data"

    def __init__(self):

        self.matcher = pathmatch.Matcher()
        self.rootLinks = []  # links from the root of the API

    @defer.inlineCallbacks
    def setServiceParent(self, parent):
        yield super().setServiceParent(parent)
        self._setup()

    def _scanModule(self, mod, _noSetattr=False):
        for sym in dir(mod):
            obj = getattr(mod, sym)
            if inspect.isclass(obj) and issubclass(obj, base.ResourceType):
                rtype = obj(self.master)
                setattr(self.rtypes, rtype.name, rtype)

                # put its update methods into our 'updates' attribute
                for name in dir(rtype):
                    o = getattr(rtype, name)
                    if hasattr(o, 'isUpdateMethod'):
                        setattr(self.updates, name, o)

                # load its endpoints
                for ep in rtype.getEndpoints():
                    # don't use inherited values for these parameters
                    clsdict = ep.__class__.__dict__
                    pathPatterns = clsdict.get('pathPatterns', '')
                    pathPatterns = pathPatterns.split()
                    pathPatterns = [tuple(pp.split('/')[1:])
                                    for pp in pathPatterns]
                    for pp in pathPatterns:
                        # special-case the root
                        if pp == ('',):
                            pp = ()
                        self.matcher[pp] = ep
                    rootLinkName = clsdict.get('rootLinkName')
                    if rootLinkName:
                        self.rootLinks.append({'name': rootLinkName})

    def _setup(self):
        self.updates = Updates()
        self.rtypes = RTypes()
        for moduleName in self.submodules:
            module = reflect.namedModule(moduleName)
            self._scanModule(module)

    def getEndpoint(self, path):
        try:
            return self.matcher[path]
        except KeyError as e:
            raise exceptions.InvalidPathError(
                "Invalid path: " + "/".join([str(p) for p in path])) from e

    def getResourceType(self, name):
        return getattr(self.rtypes, name)

    @defer.inlineCallbacks
    def get(self, path, filters=None, fields=None, order=None,
            limit=None, offset=None):
        resultSpec = resultspec.ResultSpec(filters=filters, fields=fields,
                                           order=order, limit=limit, offset=offset)
        endpoint, kwargs = self.getEndpoint(path)
        rv = yield endpoint.get(resultSpec, kwargs)
        if resultSpec:
            rv = resultSpec.apply(rv)
        return rv

    def control(self, action, args, path):
        endpoint, kwargs = self.getEndpoint(path)
        return endpoint.control(action, args, kwargs)

    def produceEvent(self, rtype, msg, event):
        # warning, this is temporary api, until all code is migrated to data
        # api
        rsrc = self.getResourceType(rtype)
        return rsrc.produceEvent(msg, event)

    @functools.lru_cache(1)
    def allEndpoints(self):
        """return the full spec of the connector as a list of dicts
        """
        paths = []
        for k, v in sorted(self.matcher.iterPatterns()):
            paths.append(dict(path="/".join(k),
                              plural=str(v.rtype.plural),
                              type=str(v.rtype.entityType.name),
                              type_spec=v.rtype.entityType.getSpec()))
        return paths

    @functools.lru_cache(1)
    def get_graphql_schema(self):
        """Return the graphQL Schema of the buildbot data model
        """
        types = {}
        schema = textwrap.dedent("""
        # custom scalar types for buildbot data model
        scalar Date   # stored as utc unix timestamp
        scalar Binary # arbitrary data stored as base85
        scalar JSON  # arbitrary json stored as string, mainly used for properties values
        """)

        # type dependencies must be added recursively
        def add_dependent_types(ent):
            typename = ent.toGraphQLTypeName()
            if typename not in types and isinstance(ent, Entity):
                types[typename] = ent
            for dtyp in ent.graphQLDependentTypes():
                add_dependent_types(dtyp)

        # root query contain the list of item available directly
        # mapped against the rootLinks
        schema += "type Query {\n"

        for rootlink in sorted(v['name'] for v in self.rootLinks):
            ep = self.matcher[(rootlink,)][0]
            typ = ep.rtype.entityType
            typename = typ.toGraphQLTypeName()
            add_dependent_types(typ)
            # build the queriable parameters, via keyFields
            keyfields = []
            for field in ep.rtype.keyFields:
                field_type = ep.rtype.entityType.fields[field].toGraphQLTypeName()
                keyfields.append(f"{field}: {field_type}")
            keyfields = ", ".join(keyfields)
            if keyfields:
                keyfields = f"({keyfields})"
            schema += f"  {ep.rtype.plural}{keyfields}: [{typename}]!\n"

        schema += "}\n"

        for name, typ in types.items():
            type_spec = typ.toGraphQL()
            schema += f"type {name} {{\n"
            for field in type_spec.get('fields', []):
                field_type = field['type']
                if not isinstance(field_type, str):
                    field_type = field_type['type']
                schema += f"  {field['name']}: {field_type}\n"
            schema += "}\n"

        return schema
