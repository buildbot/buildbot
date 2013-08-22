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

from __future__ import with_statement

import re
import fnmatch
import datetime
import types
from contextlib import contextmanager
from twisted.internet import defer
from twisted.python import log
from twisted.web import server
from buildbot.www import resource
from buildbot.data import base, resultspec
from buildbot.data import exceptions
from buildbot.util import json
from buildbot.status.web.status_json import JsonStatusResource

class BadRequest(Exception):
    pass


class BadJsonRpc2(Exception):

    def __init__(self, message, jsonrpccode):
        self.message = message
        self.jsonrpccode = jsonrpccode


class RestRootResource(resource.Resource):
    version_classes = {}

    @classmethod
    def addApiVersion(cls, version, version_cls):
        cls.version_classes[version] = version_cls
        version_cls.apiVersion = version

    def __init__(self, master):
        resource.Resource.__init__(self, master)

        min_vers = master.config.www.get('rest_minimum_version', 0)
        latest = max(self.version_classes.iterkeys())
        for version, klass in self.version_classes.iteritems():
            if version < min_vers:
                continue
            child = klass(master)
            self.putChild('v%d' % (version,), child)
            if version == latest:
                self.putChild('latest', child)

    def render(self, request):
        request.setHeader("content-type", 'application/json')
        min_vers = self.master.config.www.get('rest_minimum_version', 0)
        api_versions = dict( ('v%d' % v, '%sapi/v%d' % (self.base_url, v))
                             for v in self.version_classes
                             if v > min_vers)
        return json.dumps(dict(api_versions=api_versions))


# API version 1 was the 0.8.x status_json.py API

class V1RootResource(JsonStatusResource):
    def __init__(self, master):
        self.master = master
        JsonStatusResource.__init__(self,master.status)

URL_ENCODED = "application/x-www-form-urlencoded"
JSON_ENCODED = "application/json"
JSONRPC_CODES = dict(parse_error= -32700,
                     invalid_request= -32600,
                     method_not_found= -32601,
                     invalid_params= -32602,
                     internal_error= -32603)


class V2RootResource(resource.Resource):

    # For GETs, this API follows http://jsonapi.org.  The getter API does not
    # permit create, update, or delete, so this is limited to reading.
    #
    # Data API control methods can be invoked via a POST to the appropriate
    # URL.  These follow http://www.jsonrpc.org/specification, with a few
    # limitations:
    # - params as list is not supported
    # - rpc call batching is not supported
    # - jsonrpc2 notifications are not supported (you always get an answer)

    # rather than construct the entire possible hierarchy of Rest resources,
    # this is marked as a leaf node, and any remaining path items are parsed
    # during rendering
    isLeaf = True

    # enable reconfigResource calls
    needsReconfig = True

    def getEndpoint(self, request):
        # note that trailing slashes are not allowed
        return self.master.data.getEndpoint(tuple(request.postpath))

    @contextmanager
    def handleErrors(self, writeError):
        try:
            yield
        except exceptions.InvalidPathError, e:
            writeError(str(e) or "invalid path", errcode=404,
                    jsonrpccode=JSONRPC_CODES['invalid_request'])
            return
        except exceptions.InvalidControlException, e:
            writeError(str(e) or "invalid control action", errcode=501,
                    jsonrpccode=JSONRPC_CODES["method_not_found"])
            return
        except BadRequest, e:
            writeError(str(e) or "invalid request", errcode=400,
                    jsonrpccode=JSONRPC_CODES["method_not_found"])
            return
        except BadJsonRpc2, e:
            writeError(e.message, errcode=400, jsonrpccode=e.jsonrpccode)
            return
        except Exception, e:
            log.err(_why='while handling API request')
            writeError(repr(e), errcode=500,
                    jsonrpccode=JSONRPC_CODES["internal_error"])
            return

    ## JSONRPC2 support

    def decodeJsonRPC2(self, request):
        # Content-Type is ignored, so that AJAX requests can be sent without
        # incurring CORS preflight overheads.  The JSONRPC spec does not
        # suggest a Content-Type anyway.
        try:
            data = json.loads(request.content.read())
        except Exception,e:
            raise BadJsonRpc2("JSON parse error: %s" % (str(e),),
                    JSONRPC_CODES["parse_error"])

        if type(data) == list:
            raise BadJsonRpc2("JSONRPC batch requests are not supported",
                    JSONRPC_CODES["invalid_request"])
        if type(data) != dict:
            raise BadJsonRpc2("JSONRPC root object must be an object",
                    JSONRPC_CODES["invalid_request"])

        def check(name, types, typename):
            if name not in data:
                raise BadJsonRpc2("missing key '%s'" % (name,),
                        JSONRPC_CODES["invalid_request"])
            if not isinstance(data[name], types):
                raise BadJsonRpc2("'%s' must be %s" % (name, typename),
                        JSONRPC_CODES["invalid_request"])
        check("jsonrpc", (str,unicode), "a string")
        check("method", (str,unicode), "a string")
        check("id", (str,unicode,int,types.NoneType),
                "a string, number, or null")
        check("params", (dict,), "an object")
        if data['jsonrpc'] != '2.0':
            raise BadJsonRpc2("only JSONRPC 2.0 is supported",
                    JSONRPC_CODES['invalid_request'])
        return data["method"], data["id"], data['params']

    @defer.inlineCallbacks
    def renderJsonRpc(self, request):
        jsonRpcReply = {'jsonrpc' : "2.0"}
        def writeError(msg, errcode=399,
                jsonrpccode=JSONRPC_CODES["internal_error"]):
            if self.debug:
                log.msg("JSONRPC error: %s" % (msg,))
            request.setResponseCode(errcode)
            request.setHeader('content-type', JSON_ENCODED)
            if not "error" in jsonRpcReply: #already filled in by caller
                jsonRpcReply['error'] = dict(code=jsonrpccode, message=msg)
            request.write(json.dumps(jsonRpcReply))

        with self.handleErrors(writeError):
            method, id, params = self.decodeJsonRPC2(request)
            jsonRpcReply['id'] = id
            ep, kwargs = self.getEndpoint(request)

            result = yield ep.control(method, params, kwargs)
            jsonRpcReply['result'] = result

            data = json.dumps(jsonRpcReply, default=self._toJson,
                                    sort_keys=True, separators=(',',':'))

            request.setHeader('content-type', JSON_ENCODED)
            if request.method == "HEAD":
                request.setHeader("content-length", len(data))
                request.write('')
            else:
                request.write(data)

    ## JSONAPI support

    def decodeResultSpec(self, request, endpoint):
        reqArgs = request.args

        def checkFields(fields, negOk=False):
            for k in fields:
                if k[0] == '-' and negOk:
                    k = k[1:]
                if k not in entityType.fieldNames:
                    raise BadRequest("no such field %r" % (k,))

        entityType = endpoint.rtype.entityType
        limit = offset = order = fields = None
        filters = []
        for arg in reqArgs:
            if arg == 'order':
                order = reqArgs[arg]
                checkFields(order, True)
                continue
            elif arg == 'field':
                fields = reqArgs[arg]
                checkFields(fields, False)
                continue
            elif arg == 'limit':
                try:
                    limit = int(reqArgs[arg][0])
                except Exception:
                    raise BadRequest('invalid limit')
                continue
            elif arg == 'offset':
                try:
                    offset = int(reqArgs[arg][0])
                except Exception:
                    raise BadRequest('invalid offset')
                continue
            elif arg in entityType.fieldNames:
                field = entityType.fields[arg]
                try:
                    values = [field.valueFromString(v) for v in reqArgs[arg]]
                except Exception:
                    raise BadRequest('invalid filter value for %s' % arg)

                filters.append(resultspec.Filter(arg, 'eq', values))
                continue
            elif '__' in arg:
                field, op = arg.rsplit('__', 1)
                args = reqArgs[arg]
                operators = (resultspec.Filter.singular_operators
                                if len(args) == 1
                            else resultspec.Filter.plural_operators)
                if op in operators and field in entityType.fieldNames:
                    fieldType = entityType.fields[field]
                    try:
                        values = [fieldType.valueFromString(v)
                                for v in reqArgs[arg]]
                    except Exception:
                        raise BadRequest('invalid filter value for %s' % arg)
                    filters.append(resultspec.Filter(field, op, values))
                    continue
            raise BadRequest("unrecognized query parameter '%s'" % (arg,))

        # if ordering or filtering is on a field that's not in fields, bail out
        if fields:
            fieldsSet = set(fields)
            if order and set(order) - fieldsSet:
                raise BadRequest("cannot order on un-selected fields")
            for filter in filters:
                if filter.field not in fieldsSet:
                    raise BadRequest("cannot filter on un-selected fields")

        # bulid the result spec
        rspec = resultspec.ResultSpec(fields=fields, limit=limit,
                offset=offset, order=order, filters=filters)

        # for singular endpoints, only allow fields
        if not endpoint.isCollection:
            if rspec.filters or rspec.limit or rspec.offset:
                raise BadRequest("this is not a collection")

        return rspec

    @defer.inlineCallbacks
    def renderRest(self, request):
        def writeError(msg, errcode=404, jsonrpccode=None):
            if self.debug:
                log.msg("REST error: %s" % (msg,))
            request.setResponseCode(errcode)
            request.setHeader('content-type', 'text/plain; charset=utf-8')
            request.write(json.dumps(dict(error=msg)))

        with self.handleErrors(writeError):
            ep, kwargs = self.getEndpoint(request)

            rspec = self.decodeResultSpec(request, ep)

            data = yield ep.get(rspec, kwargs)
            if data is None:
                writeError("not found", errcode=404)
                return

            # post-process any remaining parts of the resultspec
            data = rspec.apply(data)

            # annotate the result with some metadata
            meta = {}
            links = meta['links'] = []
            ignore = set(['limit', 'offset'])
            query = [ (k,v)
                        for (k,vs) in request.args.iteritems()
                        for v in vs
                        if k not in ignore ]
            def mklink(rel, offset, limit):
                o = [('offset', offset)] if offset else []
                l = [('limit', limit)] if limit else []
                links.append({'rel': rel,
                    'href': base.Link(tuple(request.postpath),
                                    query + o + l)})

            if ep.isCollection:
                offset, total, limit = data.offset, data.total, data.limit
                if offset is None:
                    offset = 0

                # add total, if known
                if total is not None:
                    meta['total'] = total

                links = meta['links'] = []

                # add pagination links
                mklink('self', offset, limit)
                if offset != 0:
                    mklink('first', 0, limit)
                if limit:
                    prev = offset - limit
                    if prev >= 0:
                        mklink('prev', prev, limit)
                    elif offset != 0:
                        mklink('prev', 0, offset)
                if limit is not None:
                    if total is None or offset + limit < total:
                        mklink('next', offset + limit, limit)

                # get the real list instance out of the ListResult
                data = data.data
            else:
                mklink('self', None, None)
                data = [data]

            typeName = ep.rtype.plural
            data = {
                typeName: data,
                'meta': meta
            }

            # set up the content type and formatting options; if the request
            # accepts text/html or text/plain, the JSON will be rendered in a
            # readable, multiline format.

            if 'application/json' in (request.getHeader('accept') or ''):
                compact = True
                request.setHeader("content-type",
                            'application/json; charset=utf-8')
            else:
                compact = False
                request.setHeader("content-type",
                            'text/plain; charset=utf-8')

            # set up caching
            if self.cache_seconds:
                now = datetime.datetime.utcnow()
                expires = now + datetime.timedelta(seconds=self.cache_seconds)
                request.setHeader("Expires",
                                expires.strftime("%a, %d %b %Y %H:%M:%S GMT"))
                request.setHeader("Pragma", "no-cache")

            # filter out blanks if necessary and render the data
            if compact:
                data = json.dumps(data, default=self._toJson,
                                        sort_keys=True, separators=(',',':'))
            else:
                data = json.dumps(data, default=self._toJson,
                                        sort_keys=True, indent=2)

            if request.method == "HEAD":
                request.setHeader("content-length", len(data))
            else:
                request.write(data)

    def reconfigResource(self, new_config):
        # pre-translate the origin entries in the config
        self.origins = [ re.compile(fnmatch.translate(o.lower()))
                        for o in new_config.www.get('allowed_origins', []) ]

        # and copy some other flags
        self.debug = new_config.www.get('debug')
        self.cache_seconds = new_config.www.get('json_cache_seconds', 0)

    def render(self, request):
        def writeError(msg, errcode=400):
            if self.debug:
                log.msg("HTTP error: %s" % (msg,))
            request.setResponseCode(errcode)
            request.setHeader('content-type', 'text/plain; charset=utf-8')
            request.write(json.dumps(dict(error=msg)))
            request.finish()

        # Handle CORS, if necessary.
        origins = self.origins
        if origins is not None:
            isPreflight = False
            reqOrigin = request.getHeader('origin')
            if reqOrigin:
                err = None
                reqOrigin = reqOrigin.lower()
                if not any(o.match(reqOrigin) for o in self.origins):
                    err = "invalid origin"
                elif request.method == 'OPTIONS':
                    preflightMethod = request.getHeader(
                            'access-control-request-method')
                    if preflightMethod not in ('GET', 'POST', 'HEAD'):
                        err = 'invalid method'
                    isPreflight = True
                if err:
                    writeError(err)
                    return server.NOT_DONE_YET

                # If it's OK, then let the browser know we checked it out.  The
                # Content-Type header is included here because CORS considers
                # content types other than form data and text/plain to not be
                # simple.
                request.setHeader("access-control-allow-origin", reqOrigin)
                request.setHeader("access-control-allow-headers",
                                  "Content-Type")
                request.setHeader("access-control-max-age", '3600')

                # if this was a preflight request, we're done
                if isPreflight:
                    request.finish()
                    return server.NOT_DONE_YET

        # based on the method, this is either JSONRPC or REST
        if request.method == 'POST':
            d = self.renderJsonRpc(request)
        elif request.method in ('GET', 'HEAD'):
            d = self.renderRest(request)
        else:
            writeError("invalid HTTP method")
            return server.NOT_DONE_YET

        @d.addCallback
        def finish(_):
            try:
                request.finish()
            except RuntimeError: # pragma: no-cover
                # this occurs when the client has already disconnected; ignore
                # it (see #2027)
                log.msg("http client disconnected before results were sent")

        @d.addErrback
        def fail(f):
            log.err(f, 'While rendering resource:')
            try:
                writeError('internal error - see logs', errcode=500)
            except Exception:
                try:
                    request.finish()
                except:
                    pass
        return server.NOT_DONE_YET

    def _toJson(self, obj):
        if isinstance(obj, base.Link):
            return obj.makeUrl(self.base_url, self.apiVersion)

RestRootResource.addApiVersion(1, V1RootResource)
RestRootResource.addApiVersion(2, V2RootResource)
