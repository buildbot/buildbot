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

import json

from twisted.internet import defer
from twisted.python import log
from twisted.web.error import Error

from buildbot.util import bytes2unicode
from buildbot.util import unicode2bytes
from buildbot.www import resource
from buildbot.www.rest import RestRootResource


class V3RootResource(resource.Resource):
    isLeaf = True

    # enable reconfigResource calls
    needsReconfig = True

    def reconfigResource(self, new_config):
        # @todo v2 has cross origin support, which might need to be factorized
        graphql_config = new_config.www.get("graphql")
        self.debug = True
        self.graphql = None
        if graphql_config is not None:
            self.graphql = True

    def render(self, request):
        def writeError(msg, errcode=400):
            if isinstance(msg, list):
                errors = msg
            else:
                msg = bytes2unicode(msg)
                errors = [{"message": msg}]
            if self.debug:
                log.msg(f"HTTP error: {errors}")
            request.setResponseCode(errcode)
            request.setHeader(b"content-type", b"application/json; charset=utf-8")
            data = json.dumps({"data": None, "errors": errors})
            data = unicode2bytes(data)
            request.write(data)
            request.finish()

        return self.asyncRenderHelper(request, self.asyncRender, writeError)

    @defer.inlineCallbacks
    def asyncRender(self, request):
        if self.graphql is None:
            raise Error(501, "graphql not enabled")

        # graphql accepts its query either in post data or get query
        if request.method == b"POST":
            content_type = request.getHeader(b"content-type")
            if content_type == b"application/graphql":
                query = request.content.read().decode()
            elif content_type == b"application/json":
                json_query = json.load(request.content)
                query = json_query.pop('query')
                if json_query:
                    fields = " ".join(json_query.keys())
                    raise Error(400, b"json request unsupported fields: " + fields.encode())
            elif content_type is None:
                raise Error(400, b"no content-type")
            else:
                raise Error(400, b"unsupported content-type: " + content_type)

        elif request.method in (b"GET"):
            if b"query" not in request.args:
                raise Error(400, b"GET request must contain a 'query' parameter")
            query = request.args[b"query"][0].decode()
        else:
            raise Error(400, b"invalid HTTP method")

        res = yield self.master.graphql.query(query)
        errors = None
        if res.errors:
            errors = [e.formatted for e in res.errors]
        request.setHeader(b"content-type", b"application/json; charset=utf-8")
        data = json.dumps({"data": res.data, "errors": errors}).encode()
        request.write(data)


RestRootResource.addApiVersion(3, V3RootResource)
