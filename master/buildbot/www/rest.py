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

from __future__ import absolute_import
from __future__ import print_function
from future.moves.urllib.parse import urlparse
from future.utils import iteritems
from future.utils import text_type

import cgi
import datetime
import fnmatch
import json
import re
from contextlib import contextmanager

from twisted.internet import defer
from twisted.python import log
from twisted.web.error import Error

from buildbot.data import exceptions
from buildbot.data import resultspec
from buildbot.util import bytes2NativeString
from buildbot.util import bytes2unicode
from buildbot.util import toJson
from buildbot.util import unicode2bytes
from buildbot.www import resource
from buildbot.www.authz import Forbidden


class BadRequest(Exception):
    pass


class BadJsonRpc2(Exception):

    def __init__(self, message, jsonrpccode):
        self.message = message
        self.jsonrpccode = jsonrpccode


class ContentTypeParser(object):

    def __init__(self, contenttype):
        self.typeheader = contenttype

    def gettype(self):
        mimetype, options = cgi.parse_header(
            bytes2NativeString(self.typeheader))
        return mimetype


URL_ENCODED = b"application/x-www-form-urlencoded"
JSON_ENCODED = b"application/json"


class RestRootResource(resource.Resource):
    version_classes = {}

    @classmethod
    def addApiVersion(cls, version, version_cls):
        cls.version_classes[version] = version_cls
        version_cls.apiVersion = version

    def __init__(self, master):
        resource.Resource.__init__(self, master)

        min_vers = master.config.www.get('rest_minimum_version', 0)
        latest = max(list(self.version_classes))
        for version, klass in iteritems(self.version_classes):
            if version < min_vers:
                continue
            child = klass(master)
            child_path = 'v{}'.format(version)
            child_path = unicode2bytes(child_path)
            self.putChild(child_path, child)
            if version == latest:
                self.putChild(b'latest', child)

    def render(self, request):
        request.setHeader(b"content-type", JSON_ENCODED)
        min_vers = self.master.config.www.get('rest_minimum_version', 0)
        api_versions = dict(('v%d' % v, '%sapi/v%d' % (self.base_url, v))
                            for v in self.version_classes
                            if v > min_vers)
        data = json.dumps(dict(api_versions=api_versions))
        return unicode2bytes(data)


JSONRPC_CODES = dict(parse_error=-32700,
                     invalid_request=-32600,
                     method_not_found=-32601,
                     invalid_params=-32602,
                     internal_error=-32603)


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

    @defer.inlineCallbacks
    def getEndpoint(self, request, method, params):
        # note that trailing slashes are not allowed
        request_postpath = tuple(bytes2NativeString(p) for p in request.postpath)
        yield self.master.www.assertUserAllowed(request, request_postpath,
                                                method, params)
        ret = yield self.master.data.getEndpoint(request_postpath)
        defer.returnValue(ret)

    @contextmanager
    def handleErrors(self, writeError):
        try:
            yield
        except exceptions.InvalidPathError as e:
            msg = unicode2bytes(e.args[0])
            writeError(msg or b"invalid path", errcode=404,
                       jsonrpccode=JSONRPC_CODES['invalid_request'])
            return
        except exceptions.InvalidControlException as e:
            msg = unicode2bytes(str(e))
            writeError(msg or b"invalid control action", errcode=501,
                       jsonrpccode=JSONRPC_CODES["method_not_found"])
            return
        except BadRequest as e:
            msg = unicode2bytes(e.args[0])
            writeError(msg or b"invalid request", errcode=400,
                       jsonrpccode=JSONRPC_CODES["method_not_found"])
            return
        except BadJsonRpc2 as e:
            msg = unicode2bytes(e.message)
            writeError(msg, errcode=400, jsonrpccode=e.jsonrpccode)
            return
        except Forbidden as e:
            # There is nothing in jsonrc spec about forbidden error, so pick
            # invalid request
            msg = unicode2bytes(e.message)
            writeError(
                msg, errcode=403, jsonrpccode=JSONRPC_CODES["invalid_request"])
            return
        except Exception as e:
            log.err(_why='while handling API request')
            msg = unicode2bytes(repr(e))
            writeError(repr(e), errcode=500,
                       jsonrpccode=JSONRPC_CODES["internal_error"])
            return

    # JSONRPC2 support

    def decodeJsonRPC2(self, request):
        # Verify the content-type.  Browsers are easily convinced to send
        # POST data to arbitrary URLs via 'form' elements, but they won't
        # use the application/json content-type.
        if ContentTypeParser(request.getHeader(b'content-type')).gettype() != "application/json":
            raise BadJsonRpc2('Invalid content-type (use application/json)',
                              JSONRPC_CODES["invalid_request"])

        try:
            data = json.loads(bytes2NativeString(request.content.read()))
        except Exception as e:
            raise BadJsonRpc2("JSON parse error: %s" % (str(e),),
                              JSONRPC_CODES["parse_error"])

        if isinstance(data, list):
            raise BadJsonRpc2("JSONRPC batch requests are not supported",
                              JSONRPC_CODES["invalid_request"])
        if not isinstance(data, dict):
            raise BadJsonRpc2("JSONRPC root object must be an object",
                              JSONRPC_CODES["invalid_request"])

        def check(name, types, typename):
            if name not in data:
                raise BadJsonRpc2("missing key '%s'" % (name,),
                                  JSONRPC_CODES["invalid_request"])
            if not isinstance(data[name], types):
                raise BadJsonRpc2("'%s' must be %s" % (name, typename),
                                  JSONRPC_CODES["invalid_request"])
        check("jsonrpc", (str, text_type), "a string")
        check("method", (str, text_type), "a string")
        check("id", (str, text_type, int, type(None)),
              "a string, number, or null")
        check("params", (dict,), "an object")
        if data['jsonrpc'] != '2.0':
            raise BadJsonRpc2("only JSONRPC 2.0 is supported",
                              JSONRPC_CODES['invalid_request'])
        return data["method"], data["id"], data['params']

    @defer.inlineCallbacks
    def renderJsonRpc(self, request):
        jsonRpcReply = {'jsonrpc': "2.0"}

        def writeError(msg, errcode=399,
                       jsonrpccode=JSONRPC_CODES["internal_error"]):
            msg = bytes2NativeString(msg)
            if self.debug:
                log.msg("JSONRPC error: %s" % (msg,))
            request.setResponseCode(errcode)
            request.setHeader(b'content-type', JSON_ENCODED)
            if "error" not in jsonRpcReply:  # already filled in by caller
                jsonRpcReply['error'] = dict(code=jsonrpccode, message=msg)
            data = json.dumps(jsonRpcReply)
            data = unicode2bytes(data)
            request.write(data)

        with self.handleErrors(writeError):
            method, id, params = self.decodeJsonRPC2(request)
            jsonRpcReply['id'] = id
            ep, kwargs = yield self.getEndpoint(request, method, params)
            userinfos = self.master.www.getUserInfos(request)
            if 'anonymous' in userinfos and userinfos['anonymous']:
                owner = "anonymous"
            else:
                owner = userinfos['email']
            params['owner'] = owner

            result = yield ep.control(method, params, kwargs)
            jsonRpcReply['result'] = result

            data = json.dumps(jsonRpcReply, default=toJson,
                              sort_keys=True, separators=(',', ':'))

            request.setHeader(b'content-type', JSON_ENCODED)
            if request.method == b"HEAD":
                request.setHeader(b"content-length", len(data))
                request.write(b'')
            else:
                data = unicode2bytes(data)
                request.write(data)

    # JSONAPI support
    def decodeResultSpec(self, request, endpoint):
        reqArgs = request.args

        def checkFields(fields, negOk=False):
            for field in fields:
                k = bytes2NativeString(field)
                if k[0] == '-' and negOk:
                    k = k[1:]
                if k not in entityType.fieldNames:
                    raise BadRequest("no such field '{}'".format(k))

        entityType = endpoint.rtype.entityType
        limit = offset = order = fields = None
        filters, properties = [], []
        for arg in reqArgs:
            argStr = bytes2NativeString(arg)
            if arg == b'order':
                order = tuple([bytes2NativeString(o) for o in reqArgs[arg]])
                checkFields(order, True)
                continue
            elif arg == b'field':
                fields = reqArgs[arg]
                checkFields(fields, False)
                continue
            elif arg == b'limit':
                try:
                    limit = int(reqArgs[arg][0])
                except Exception:
                    raise BadRequest('invalid limit')
                continue
            elif arg == b'offset':
                try:
                    offset = int(reqArgs[arg][0])
                except Exception:
                    raise BadRequest('invalid offset')
                continue
            elif arg == b'property':
                try:
                    props = []
                    for v in reqArgs[arg]:
                        if not isinstance(v, (bytes, text_type)):
                            raise TypeError(
                                "Invalid type {} for {}".format(type(v), v))
                        props.append(bytes2unicode(v))
                except Exception:
                    raise BadRequest(
                        'invalid property value for {}'.format(arg))
                properties.append(resultspec.Property(arg, 'eq', props))
                continue
            elif argStr in entityType.fieldNames:
                field = entityType.fields[argStr]
                try:
                    values = [field.valueFromString(v) for v in reqArgs[arg]]
                except Exception:
                    raise BadRequest(
                        'invalid filter value for {}'.format(argStr))

                filters.append(resultspec.Filter(argStr, 'eq', values))
                continue
            elif '__' in argStr:
                field, op = argStr.rsplit('__', 1)
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
                        raise BadRequest(
                            'invalid filter value for {}'.format(argStr))
                    filters.append(resultspec.Filter(field, op, values))
                    continue
            raise BadRequest(
                "unrecognized query parameter '{}'".format(argStr))

        # if ordering or filtering is on a field that's not in fields, bail out
        if fields:
            fields = [bytes2NativeString(f) for f in fields]
            fieldsSet = set(fields)
            if order and set([o.lstrip('-') for o in order]) - fieldsSet:
                raise BadRequest("cannot order on un-selected fields")
            for filter in filters:
                if filter.field not in fieldsSet:
                    raise BadRequest("cannot filter on un-selected fields")

        # build the result spec
        rspec = resultspec.ResultSpec(fields=fields, limit=limit, offset=offset,
                                      order=order, filters=filters, properties=properties)

        # for singular endpoints, only allow fields
        if not endpoint.isCollection:
            if rspec.filters:
                raise BadRequest("this is not a collection")

        return rspec

    def encodeRaw(self, data, request):
        request.setHeader(b"content-type",
                          data['mime-type'].encode() + b'; charset=utf-8')
        request.setHeader(b"content-disposition",
                          b'attachment; filename=' + data['filename'].encode())
        request.write(data['raw'].encode('utf-8'))
        return

    @defer.inlineCallbacks
    def renderRest(self, request):
        def writeError(msg, errcode=404, jsonrpccode=None):
            if self.debug:
                log.msg("REST error: %s" % (msg,))
            request.setResponseCode(errcode)
            request.setHeader(b'content-type', b'text/plain; charset=utf-8')
            msg = bytes2NativeString(msg)
            data = json.dumps(dict(error=msg))
            data = unicode2bytes(data)
            request.write(data)

        with self.handleErrors(writeError):
            ep, kwargs = yield self.getEndpoint(request, bytes2NativeString(request.method), {})

            rspec = self.decodeResultSpec(request, ep)
            data = yield ep.get(rspec, kwargs)
            if data is None:
                msg = ("not found while getting from {} with "
                       "arguments {} and {}").format(repr(ep), repr(rspec),
                                                     str(kwargs))
                msg = unicode2bytes(msg)
                writeError(msg, errcode=404)
                return

            if ep.isRaw:
                self.encodeRaw(data, request)
                return

            # post-process any remaining parts of the resultspec
            data = rspec.apply(data)

            # annotate the result with some metadata
            meta = {}
            if ep.isCollection:
                offset, total = data.offset, data.total
                if offset is None:
                    offset = 0

                # add total, if known
                if total is not None:
                    meta['total'] = total

                # get the real list instance out of the ListResult
                data = data.data
            else:
                data = [data]

            typeName = ep.rtype.plural
            data = {
                typeName: data,
                'meta': meta
            }

            # set up the content type and formatting options; if the request
            # accepts text/html or text/plain, the JSON will be rendered in a
            # readable, multiline format.

            if b'application/json' in (request.getHeader(b'accept') or b''):
                compact = True
                request.setHeader(b"content-type",
                                  b'application/json; charset=utf-8')
            else:
                compact = False
                request.setHeader(b"content-type",
                                  b'text/plain; charset=utf-8')

            # set up caching
            if self.cache_seconds:
                now = datetime.datetime.utcnow()
                expires = now + datetime.timedelta(seconds=self.cache_seconds)
                expiresBytes = unicode2bytes(
                    expires.strftime("%a, %d %b %Y %H:%M:%S GMT"))
                request.setHeader(b"Expires", expiresBytes)
                request.setHeader(b"Pragma", b"no-cache")

            # filter out blanks if necessary and render the data
            if compact:
                data = json.dumps(data, default=toJson,
                                  sort_keys=True, separators=(',', ':'))
            else:
                data = json.dumps(data, default=toJson,
                                  sort_keys=True, indent=2)

            if request.method == b"HEAD":
                request.setHeader(b"content-length", len(data))
            else:
                data = unicode2bytes(data)
                request.write(data)

    def reconfigResource(self, new_config):
        # buildbotURL may contain reverse proxy path, Origin header is just
        # scheme + host + port
        buildbotURL = urlparse(unicode2bytes(new_config.buildbotURL))
        origin_self = buildbotURL.scheme + b"://" + buildbotURL.netloc
        # pre-translate the origin entries in the config
        self.origins = []
        for o in new_config.www.get('allowed_origins', [origin_self]):
            origin = bytes2NativeString(o).lower()
            self.origins.append(re.compile(fnmatch.translate(origin)))

        # and copy some other flags
        self.debug = new_config.www.get('debug')
        self.cache_seconds = new_config.www.get('json_cache_seconds', 0)

    def render(self, request):
        def writeError(msg, errcode=400):
            msg = bytes2NativeString(msg)
            if self.debug:
                log.msg("HTTP error: %s" % (msg,))
            request.setResponseCode(errcode)
            request.setHeader(b'content-type', b'text/plain; charset=utf-8')
            if request.method == b'POST':
                # jsonRPC callers want the error message in error.message
                data = json.dumps(dict(error=dict(message=msg)))
                data = unicode2bytes(data)
                request.write(data)
            else:
                data = json.dumps(dict(error=msg))
                data = unicode2bytes(data)
                request.write(data)
            request.finish()
        return self.asyncRenderHelper(request, self.asyncRender, writeError)

    @defer.inlineCallbacks
    def asyncRender(self, request):

        # Handle CORS, if necessary.
        origins = self.origins
        if origins is not None:
            isPreflight = False
            reqOrigin = request.getHeader(b'origin')
            if reqOrigin:
                err = None
                reqOrigin = reqOrigin.lower()
                if not any(o.match(bytes2NativeString(reqOrigin)) for o in self.origins):
                    err = "invalid origin"
                elif request.method == b'OPTIONS':
                    preflightMethod = request.getHeader(
                        b'access-control-request-method')
                    if preflightMethod not in (b'GET', b'POST', b'HEAD'):
                        err = b'invalid method'
                    isPreflight = True
                if err:
                    raise Error(400, err)

                # If it's OK, then let the browser know we checked it out.  The
                # Content-Type header is included here because CORS considers
                # content types other than form data and text/plain to not be
                # simple.
                request.setHeader(b"access-control-allow-origin", reqOrigin)
                request.setHeader(b"access-control-allow-headers",
                                  b"Content-Type")
                request.setHeader(b"access-control-max-age", b'3600')

                # if this was a preflight request, we're done
                if isPreflight:
                    defer.returnValue(b"")

        # based on the method, this is either JSONRPC or REST
        if request.method == b'POST':
            res = yield self.renderJsonRpc(request)
        elif request.method in (b'GET', b'HEAD'):
            res = yield self.renderRest(request)
        else:
            raise Error(400, b"invalid HTTP method")

        defer.returnValue(res)


RestRootResource.addApiVersion(2, V2RootResource)
