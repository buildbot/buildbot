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

from twisted.internet import defer
from twisted.python import reflect

from buildbot.data import base
from buildbot.data import exceptions
from buildbot.data import resultspec
from buildbot.util import bytes2unicode
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
                setattr(self.plural_rtypes, rtype.plural, rtype)
                self.graphql_rtypes[rtype.entityType.toGraphQLTypeName()] = rtype
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
        self.graphql_rtypes = {}
        self.rtypes = RTypes()
        self.plural_rtypes = RTypes()
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
        return getattr(self.rtypes, name, None)

    def getEndPointForResourceName(self, name):
        rtype = getattr(self.rtypes, name, None)
        rtype_plural = getattr(self.plural_rtypes, name, None)
        if rtype is not None:
            return rtype.getDefaultEndpoint()
        elif rtype_plural is not None:
            return rtype_plural.getCollectionEndpoint()
        return None

    def getResourceTypeForGraphQlType(self, type):
        if type not in self.graphql_rtypes:
            raise RuntimeError(f"Can't get rtype for {type}: {self.graphql_rtypes.keys()}")
        return self.graphql_rtypes.get(type)

    def get(self, path, filters=None, fields=None, order=None,
            limit=None, offset=None):
        resultSpec = resultspec.ResultSpec(filters=filters, fields=fields,
                                           order=order, limit=limit, offset=offset)
        return self.get_with_resultspec(path, resultSpec)

    @defer.inlineCallbacks
    def get_with_resultspec(self, path, resultSpec):
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

    def resultspec_from_jsonapi(self, req_args, entityType, is_collection):

        def checkFields(fields, negOk=False):
            for field in fields:
                k = bytes2unicode(field)
                if k[0] == '-' and negOk:
                    k = k[1:]
                if k not in entityType.fieldNames:
                    raise exceptions.InvalidQueryParameter(f"no such field '{k}'")

        limit = offset = order = fields = None
        filters, properties = [], []
        limit = offset = order = fields = None
        filters, properties = [], []
        for arg in req_args:
            argStr = bytes2unicode(arg)
            if argStr == 'order':
                order = tuple(bytes2unicode(o) for o in req_args[arg])
                checkFields(order, True)
            elif argStr == 'field':
                fields = req_args[arg]
                checkFields(fields, False)
            elif argStr == 'limit':
                try:
                    limit = int(req_args[arg][0])
                except Exception as e:
                    raise exceptions.InvalidQueryParameter('invalid limit') from e
            elif argStr == 'offset':
                try:
                    offset = int(req_args[arg][0])
                except Exception as e:
                    raise exceptions.InvalidQueryParameter('invalid offset') from e
            elif argStr == 'property':
                try:
                    props = []
                    for v in req_args[arg]:
                        if not isinstance(v, (bytes, str)):
                            raise TypeError(f"Invalid type {type(v)} for {v}")
                        props.append(bytes2unicode(v))
                except Exception as e:
                    raise exceptions.InvalidQueryParameter(
                        f'invalid property value for {arg}') from e
                properties.append(resultspec.Property(arg, 'eq', props))
            elif argStr in entityType.fieldNames:
                field = entityType.fields[argStr]
                try:
                    values = [field.valueFromString(v) for v in req_args[arg]]
                except Exception as e:
                    raise exceptions.InvalidQueryParameter(
                        f'invalid filter value for {argStr}') from e

                filters.append(resultspec.Filter(argStr, 'eq', values))
            elif '__' in argStr:
                field, op = argStr.rsplit('__', 1)
                args = req_args[arg]
                operators = (resultspec.Filter.singular_operators
                             if len(args) == 1
                             else resultspec.Filter.plural_operators)
                if op in operators and field in entityType.fieldNames:
                    fieldType = entityType.fields[field]
                    try:
                        values = [fieldType.valueFromString(v)
                                  for v in req_args[arg]]
                    except Exception as e:
                        raise exceptions.InvalidQueryParameter(
                            f'invalid filter value for {argStr}') from e
                    filters.append(resultspec.Filter(field, op, values))
            else:
                raise exceptions.InvalidQueryParameter(f"unrecognized query parameter '{argStr}'")

        # if ordering or filtering is on a field that's not in fields, bail out
        if fields:
            fields = [bytes2unicode(f) for f in fields]
            fieldsSet = set(fields)
            if order and {o.lstrip('-') for o in order} - fieldsSet:
                raise exceptions.InvalidQueryParameter("cannot order on un-selected fields")
            for filter in filters:
                if filter.field not in fieldsSet:
                    raise exceptions.InvalidQueryParameter("cannot filter on un-selected fields")

        # build the result spec
        rspec = resultspec.ResultSpec(fields=fields, limit=limit, offset=offset,
                                      order=order, filters=filters, properties=properties)

        # for singular endpoints, only allow fields
        if not is_collection:
            if rspec.filters:
                raise exceptions.InvalidQueryParameter("this is not a collection")

        return rspec
