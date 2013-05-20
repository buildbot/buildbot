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

import datetime
import re
from twisted.internet import defer
from twisted.python import log
from twisted.web import server
from buildbot.www import resource
from buildbot.data import base, exceptions as data_exceptions
from buildbot.util import json
from buildbot.status.web.status_json import JsonStatusResource

class RestRootResource(resource.Resource):
    version_classes = {}

    @classmethod
    def addApiVersion(cls, version, version_cls):
        cls.version_classes[version] = version_cls
        version_cls.apiVersion = version

    def __init__(self, master):
        resource.Resource.__init__(self, master)

        min_vers = master.config.www.get('rest_minimum_version', 0)
        for version, klass in self.version_classes.iteritems():
            if version >= min_vers:
                self.putChild('v%d' % version, klass(master))

        latest = max(self.version_classes.iterkeys())
        self.putChild('latest', self.version_classes[latest](master))

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
    # rather than construct the entire possible hierarchy of Rest resources,
    # this is marked as a leaf node, and any remaining path items are parsed
    # during rendering
    isLeaf = True

    knownArgs = set(['as_text', 'filter', 'compact', 'callback'])
    def decodeUrlEncoding(self, request):
        # calculate the request options. paging defaults
        reqOptions = {"start":0,"count":50}
        for option in set(request.args) - self.knownArgs:
            reqOptions[option] = request.args[option][0]
        _range = request.getHeader('X-Range') or request.getHeader('Range') or ""
        if _range.startswith("items="):
            try:
                start, end = map(int,_range.split("=")[1].split("-"))
                reqOptions["start"] = start
                reqOptions["count"] = end-start
            except:
                raise ValueError("bad Range/X-Range header")

        if "sort" in reqOptions:
            def convert(s):
                s = s.strip()
                if s.startswith('+'):
                    return(s[1:],0)
                if s.startswith('-'):
                    return(s[1:],1)
                return (s,0)
            reqOptions["sort"] = map(convert,reqOptions['sort'].split(','))

        return reqOptions
    def decodeJsonRPC2(self, request, reply):
        """ In the case of json encoding, we choose jsonrpc2 as the encoding:
        http://www.jsonrpc.org/specification
        instead of just inventing our own. This allow easier re-use of client side code
        This implementation is rather simple, and is not supporting all the features of jsonrpc:
        -> params as list is not supported
        -> rpc call batch is not supported
        -> jsonrpc2 notifications are not supported (i.e. you always get an answer)
       """
        datastr = request.content.read()
        def updateError(msg, jsonrpccode,e=None):
            reply.update(dict(error=dict(code=jsonrpccode,
                                   message=msg)))
            if e:
                raise e
            else:
                raise ValueError(msg)

        try:
            data = json.loads(datastr)
        except Exception,e:
            updateError("jsonrpc parse error: %s"%(str(e)), JSONRPC_CODES["parse_error"])
        if type(data) == list:
            updateError("jsonrpc call batch is not supported", JSONRPC_CODES["internal_error"])
        if type(data) != dict:
            updateError("json root object must be a dictionary: "+datastr, JSONRPC_CODES["parse_error"])

        def check(name, _types, _val=None):
            if not name in data:
                updateError("need '%s' to be present"%(name), JSONRPC_CODES["invalid_request"])
            if _types and not type(data[name]) in _types:
                updateError("need '%s' to be of type %s:%s"%(name, " or ".join(map(str,_types)), json.dumps(data[name])), JSONRPC_CODES["invalid_request"])
            if _val != None and data[name] != _val:
                updateError("need '%s' value to be '%s'"%(name, str(_val)), JSONRPC_CODES["invalid_request"])
        check("jsonrpc", (str,unicode), "2.0")
        check("method", (str,unicode))
        check("id", None)
        check("params", (dict,)) # params can be a list in jsonrpc, but we dont support it.
        reply["id"] = data["id"]
        return data["params"], data["method"]
    def render(self, request):
        @defer.inlineCallbacks
        def render():
            reqPath = request.postpath
            jsonRpcReply = dict(jsonrpc="2.0",id=None)
            # strip an empty string from the end (trailing slash)
            if reqPath and reqPath[-1] == '':
                reqPath = reqPath[:-1]

            def write_error_default(msg, errcode=404, jsonrpccode=None):
                request.setResponseCode(errcode)
                # prefer text/plain here, since this is most likely user error
                request.setHeader('content-type', 'text/plain')
                request.write(json.dumps(dict(error=msg)))

            def write_error_jsonrpc(msg, errcode=400, jsonrpccode=JSONRPC_CODES["internal_error"]):
                request.setResponseCode(errcode)
                request.setHeader('content-type', JSON_ENCODED)
                if not "error" in jsonRpcReply: #already filled in by caller
                    jsonRpcReply.update(dict(error=dict(code=jsonrpccode,
                                                        message=msg)))
                request.write(json.dumps(jsonRpcReply))
            write_error = write_error_default
            contenttype = request.getHeader('content-type') or URL_ENCODED

            if contenttype.startswith(JSON_ENCODED):
                write_error = write_error_jsonrpc
                try:
                    reqOptions, action = self.decodeJsonRPC2(request,jsonRpcReply)
                except ValueError,e:
                    write_error(str(e), jsonrpccode=JSONRPC_CODES["invalid_request"])
                    return
            else:
                reqOptions = self.decodeUrlEncoding(request)
                if request.method == "POST":
                    if not "action" in reqOptions:
                        write_error("need an action parameter for POST", errcode=400)
                        return
                    action = reqOptions["action"]
                    del reqOptions["action"]
            # get the value
            try:
                if request.method == "POST":
                    data = yield self.master.data.control(action, reqOptions, tuple(reqPath))
                else:
                    data = yield self.master.data.get(tuple(reqPath))
            except data_exceptions.InvalidPathError,e:
                write_error(str(e) or "invalid path", errcode=404)
                return
            except data_exceptions.InvalidOptionException,e:
                write_error(str(e) or "invalid option")
                return
            except data_exceptions.InvalidActionException,e:
                write_error(str(e) or "invalid method", errcode=501,jsonrpccode=JSONRPC_CODES["method_not_found"])
                return
            except Exception, e:
                write_error(repr(e), errcode=500,jsonrpccode=JSONRPC_CODES["internal_error"])
                log.err(e) # make sure we log unknown exception
                return
            if data is None and request.method=="GET":
                write_error("no data")
                return
            # format the output based on request parameters
            as_text = self._booleanArg(request, 'as_text', False)
            filter = self._booleanArg(request, 'filter', as_text)
            compact = self._booleanArg(request, 'compact', not as_text)
            callback = request.args.get('callback', [None])[0]

            if type(data) == list:
                total = reqOptions["count"] = len(data)
                if "total" in reqOptions:
                    total = reqOptions["total"]
                if reqOptions["count"] != total:
                    request.setResponseCode(206) # avoid proxy caching!

                request.setHeader("Content-Range", 'items %d-%d/%d'%(reqOptions["start"],
                                                                     reqOptions["start"]+
                                                                     reqOptions["count"],
                                                                     total))
            # set up the content type
            if as_text:
                request.setHeader("content-type", 'text/plain')
            else:
                request.setHeader("content-type", JSON_ENCODED)
                request.setHeader("content-disposition",
                            "attachment; filename=\"%s.json\"" % request.path)

            # set up caching
            cache_seconds = self.master.config.www.get('json_cache_seconds', 0)
            if cache_seconds:
                now = datetime.datetime.utcnow()
                expires = now + datetime.timedelta(seconds=cache_seconds)
                request.setHeader("Expires",
                                expires.strftime("%a, %d %b %Y %H:%M:%S GMT"))
                request.setHeader("Pragma", "no-cache")

            # filter and render the data
            if filter:
                data = self._filterEmpty(data)

            # if we are talking jsonrpc, we embed the result in standard encapsulation
            if jsonRpcReply['id'] is not None:
                jsonRpcReply.update({"result": data})
                data = jsonRpcReply

            if compact:
                data = json.dumps(data, default=self._render_links,
                                        sort_keys=True, separators=(',',':'))
            else:
                data = json.dumps(data, default=self._render_links,
                                        sort_keys=True, indent=2)

            if isinstance(data, unicode):
                data = data.encode("utf-8")

            if callback:
                # Only accept things that look like identifiers for now
                if re.match(r'^[a-zA-Z$][a-zA-Z$0-9.]*$', callback):
                    data = '%s(%s);' % (callback, data)
                request.setHeader("Access-Control-Allow-Origin", "*")

            if isinstance(data, unicode):
                data = data.encode("utf-8")
            if request.method == "HEAD":
                request.setHeader("content-length", len(data))
                request.write('')
            else:
                request.write(data)

        d = render()
        @d.addCallback
        def finish(_):
            try:
                request.finish()
            except RuntimeError:
                # this occurs when the client has already disconnected; ignore
                # it (see #2027)
                log.msg("http client disconnected before results were sent")

        @d.addErrback
        def fail(f):
            log.err(f, 'ugh')
            request.processingFailed(f)
            return None
        return server.NOT_DONE_YET

        @d.addErrback
        def eb(f):
            request.processingFailed(f)
            return None

    def _booleanArg(self, request, arg, default):
        value = request.args.get(arg, [default])[0]
        if value in (False, True):
            return value
        value = value.lower()
        if value in ('1', 'true'):
            return True
        if value in ('0', 'false'):
            return False
        # Ignore value.
        return default

    def _filterEmpty(self, data):
        empty = ('', False, None, [], {}, ())
        if isinstance(data, (list, tuple)):
            filtered = (self._filterEmpty(x) for x in data)
            return [ x for x in filtered if x not in empty ]
        elif isinstance(data, dict):
            filtered = ((k, self._filterEmpty(v))
                        for (k, v) in data.iteritems())
            return dict(x for x in filtered if x[1] not in empty)
        else:
            return data

    def _render_links(self, obj):
        if isinstance(obj, base.Link):
            return obj.makeUrl(self.base_url, self.apiVersion)

RestRootResource.addApiVersion(1, V1RootResource)
RestRootResource.addApiVersion(2, V2RootResource)
