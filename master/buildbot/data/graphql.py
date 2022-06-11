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


import asyncio
import functools
import sys
import textwrap

from buildbot.asyncio import AsyncIOLoopWithTwisted
from buildbot.asyncio import as_deferred
from buildbot.asyncio import as_future
from buildbot.data import resultspec
from buildbot.data.types import Entity
from buildbot.util import service

try:
    import graphql
    from graphql.execution.execute import default_field_resolver
except ImportError:  # pragma: no cover
    graphql = None


def _enforce_list(v):
    if isinstance(v, list):
        return v
    return [v]


class GraphQLConnector(service.AsyncService):
    """Mixin class to separate the GraphQL traits for the data connector

    This class needs to use some async methods in the asyncio domain (instead of twisted)
    await in those domains are not compatible, and must be prefixed with as_deferred / as_future

    any method doing so must be prefixed with "_aio_" to indicate that their return value should
    be transformed with as_deferred, and they should themselves transform normal data api results
    with as_future()
    """
    data = None
    asyncio_loop = None

    # asyncio will create an event loop if none exists yet in get_event_loop(). We need to set it
    # back via set_event_loop() if we want it to be properly closed.
    _saved_event_loop = None

    def reconfigServiceWithBuildbotConfig(self, new_config):
        if self.data is None:
            self.data = self.master.data
        config = new_config.www.get('graphql')
        self.enabled = False
        if config is None:
            return

        if graphql is None:
            raise ImportError("graphql is enabled but 'graphql-core' is not installed")

        self.enabled = True
        self.config = config
        loop = None
        try:
            if self._saved_event_loop is None:
                # Ideally we would like to use asyncio.get_event_loop() here. However, its API
                # makes it hard to use: the behavior depends on the current asyncio policy and
                # the default policy will create a new loop for the main thread if a loop was not
                # set before. Unfortunately we can't know whether a new loop was created,
                # and as a result we can't cleanup it in stopService(). Specifically, we can't
                # call the close() function, which results in occasional ResourceWarnings because
                # there is no one who would close the created loop.
                #
                # Using asyncio.get_running_loop() would potentially break if non-default asyncio
                # policy was used. The default policy is fine because separate threads have
                # separate event loops. Fortunately Buildbot does not change the default asyncio
                # policy, so this concern does not matter in practice.
                #
                # Note that asyncio.get_event_loop() is deprecated in favor of get_running_loop()
                if sys.version_info[:2] >= (3, 7):
                    loop = asyncio.get_running_loop()
                else:
                    loop = asyncio.get_event_loop()
        except RuntimeError:
            # get_running_loop throws if there's no current loop.
            # get_event_loop throws is there's no current loop and we're not on main thread.
            pass

        if self._saved_event_loop is None and not isinstance(loop, AsyncIOLoopWithTwisted):
            self._saved_event_loop = loop
            self.asyncio_loop = AsyncIOLoopWithTwisted(self.master.reactor)
            asyncio.set_event_loop(self.asyncio_loop)
            self.asyncio_loop.start()

        self.debug = self.config.get("debug")
        self.schema = graphql.build_schema(self.get_schema())

    def stopService(self):
        if self.asyncio_loop:
            self.asyncio_loop.stop()
            self.asyncio_loop.close()
            # We want to restore the original event loop value even if was None because otherwise
            # we would be leaving our closed AsyncIOLoopWithTwisted instance as the event loop
            asyncio.set_event_loop(self._saved_event_loop)
            self.asyncio_loop = None

        return super().stopService()

    @functools.lru_cache(1)
    def get_schema(self):
        """Return the graphQL Schema of the buildbot data model"""
        types = {}
        schema = textwrap.dedent(
            """
        # custom scalar types for buildbot data model
        scalar Date   # stored as utc unix timestamp
        scalar Binary # arbitrary data stored as base85
        scalar JSON  # arbitrary json stored as string, mainly used for properties values
        """
        )

        # type dependencies must be added recursively
        def add_dependent_types(ent):
            typename = ent.toGraphQLTypeName()
            if typename in types:
                return
            if isinstance(ent, Entity):
                types[typename] = ent
            for dtyp in ent.graphQLDependentTypes():
                add_dependent_types(dtyp)

            rtype = self.data.getResourceType(ent.name)
            if rtype is not None:
                for subresource in rtype.subresources:
                    rtype = self.data.getResourceTypeForGraphQlType(subresource)
                    add_dependent_types(rtype.entityType)

        # root query contain the list of item available directly
        # mapped against the rootLinks
        queries_schema = ""

        def format_query_fields(query_fields):
            query_fields = ",\n   ".join(query_fields)
            if query_fields:
                query_fields = f"({query_fields})"
            return query_fields

        def format_subresource(rtype):
            queries_schema = ""
            typ = rtype.entityType
            typename = typ.toGraphQLTypeName()
            add_dependent_types(typ)
            query_fields = []
            # build the queriable parameters, via query_fields
            for field, field_type in sorted(rtype.entityType.fields.items()):
                # in graphql, we handle properties as queriable sub resources
                # instead of hardcoded attributes like in rest api
                if field == 'properties':
                    continue
                field_type_graphql = field_type.getGraphQLInputType()
                if field_type_graphql is None:
                    continue
                query_fields.append(f"{field}: {field_type_graphql}")
                for op in sorted(operators):
                    if op in ["in", "notin"]:
                        if field_type_graphql in ["String", "Int"]:
                            query_fields.append(
                                f"{field}__{op}: [{field_type_graphql}]")
                    else:
                        query_fields.append(f"{field}__{op}: {field_type_graphql}")

            query_fields.extend(["order: String", "limit: Int", "offset: Int"])
            ep = self.data.getEndPointForResourceName(rtype.plural)
            if ep is None or not ep.isPseudoCollection:
                plural_typespec = f"[{typename}]"
            else:
                plural_typespec = typename
            queries_schema += (
                f"  {rtype.plural}{format_query_fields(query_fields)}: {plural_typespec}!\n"
            )

            # build the queriable parameter, via keyField
            keyfields = []
            field = rtype.keyField
            if field not in rtype.entityType.fields:
                raise RuntimeError(f"bad keyField {field} not in entityType {rtype.entityType}")
            field_type = rtype.entityType.fields[field]
            field_type_graphql = field_type.toGraphQLTypeName()
            keyfields.append(f"{field}: {field_type_graphql}")

            queries_schema += (
                f"  {rtype.name}{format_query_fields(keyfields)}: {typename}\n"
            )
            return queries_schema

        operators = set(resultspec.Filter.singular_operators)
        operators.update(resultspec.Filter.plural_operators)
        for rootlink in sorted(v["name"] for v in self.data.rootLinks):
            ep = self.data.matcher[(rootlink,)][0]
            queries_schema += format_subresource(ep.rtype)

        schema += "type Query {\n" + queries_schema + "}\n"
        schema += "type Subscription {\n" + queries_schema + "}\n"

        for name, typ in types.items():
            type_spec = typ.toGraphQL()
            schema += f"type {name} {{\n"
            for field in type_spec.get("fields", []):
                field_type = field["type"]
                if not isinstance(field_type, str):
                    field_type = field_type["type"]
                schema += f"  {field['name']}: {field_type}\n"

            rtype = self.data.getResourceType(typ.name)
            if rtype is not None:
                for subresource in rtype.subresources:
                    rtype = self.data.getResourceTypeForGraphQlType(subresource)
                    schema += format_subresource(rtype)
            schema += "}\n"
        return schema

    async def _aio_ep_get(self, ep, kwargs, resultSpec):
        rv = await as_future(ep.get(resultSpec, kwargs))
        if resultSpec:
            rv = resultSpec.apply(rv)
        return rv

    async def _aio_query(self, query):
        query = graphql.parse(query)
        errors = graphql.validate(self.schema, query)
        if errors:
            r = graphql.execution.ExecutionResult()
            r.errors = errors
            return r

        async def field_resolver(parent, resolve_info, **args):
            field = resolve_info.field_name
            if parent is not None and field in parent:
                res = default_field_resolver(parent, resolve_info, **args)
                if isinstance(res, list) and args:
                    ep = self.data.getEndPointForResourceName(field)
                    args = {k: _enforce_list(v) for k, v in args.items()}
                    rspec = self.data.resultspec_from_jsonapi(args, ep.rtype.entityType, True)
                    res = rspec.apply(res)
                return res
            ep = self.data.getEndPointForResourceName(field)
            rspec = None
            kwargs = ep.get_kwargs_from_graphql(parent, resolve_info, args)

            if ep.isCollection or ep.isPseudoCollection:
                args = {k: _enforce_list(v) for k, v in args.items()}
                rspec = self.data.resultspec_from_jsonapi(args, ep.rtype.entityType, True)

            return await self._aio_ep_get(ep, kwargs, rspec)

        # Execute
        res = await graphql.execute(
            self.schema,
            query,
            field_resolver=field_resolver,
        )
        return res

    def query(self, query):
        return as_deferred(self._aio_query(query))
