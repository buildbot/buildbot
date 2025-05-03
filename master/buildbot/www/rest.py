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

import datetime
import fnmatch
import json
import re
from contextlib import contextmanager
from typing import TYPE_CHECKING
from typing import Any
from typing import Callable
from typing import Iterator
from urllib.parse import urlparse

from twisted.internet import defer
from twisted.internet import threads
from twisted.internet.error import ConnectionDone
from twisted.python import log
from twisted.web.error import Error
from twisted.web.resource import EncodingResourceWrapper
from twisted.web.server import GzipEncoderFactory

from buildbot.data import exceptions
from buildbot.data.base import EndpointKind
from buildbot.data.resultspec import ResultSpec
from buildbot.util import bytes2unicode
from buildbot.util import toJson
from buildbot.util import unicode2bytes
from buildbot.www import resource
from buildbot.www.authz import Forbidden
from buildbot.www.encoding import BrotliEncoderFactory
from buildbot.www.encoding import ZstandardEncoderFactory

if TYPE_CHECKING:
    from typing import Any

    from twisted.web import server

    from buildbot.data.base import Endpoint
    from buildbot.data.resultspec import ResultSpec
    from buildbot.master import BuildMaster
    from buildbot.util.twisted import InlineCallbacksType


class BadJsonRpc2(Exception):
    def __init__(self, message: str, jsonrpccode: int) -> None:
        self.message = message
        self.jsonrpccode = jsonrpccode


class ContentTypeParser:
    def __init__(self, contenttype: str | bytes | None) -> None:
        self.typeheader = contenttype

    def gettype(self) -> str | None:
        if self.typeheader is None:
            return None
        return bytes2unicode(self.typeheader).split(';', 1)[0]


def _is_request_finished(request: server.Request) -> bool:
    # In case of lost connection, request is not marked as finished
    # detect this case with `channel` being None
    return bool(request.finished) or request.channel is None


URL_ENCODED = b"application/x-www-form-urlencoded"
JSON_ENCODED = b"application/json"


class RestRootResource(resource.Resource):
    version_classes: dict[int, type[V2RootResource]] = {}

    @classmethod
    def addApiVersion(cls, version: int, version_cls: type[V2RootResource]) -> None:
        cls.version_classes[version] = version_cls
        version_cls.apiVersion = version  # type: ignore[attr-defined]

    def __init__(self, master: BuildMaster) -> None:
        super().__init__(master)

        min_vers = master.config.www.get('rest_minimum_version', 0)
        encoders = [
            BrotliEncoderFactory(),
            ZstandardEncoderFactory(),
            GzipEncoderFactory(),
        ]

        latest = max(list(self.version_classes))
        for version, klass in self.version_classes.items():
            if version < min_vers:
                continue
            child = EncodingResourceWrapper(klass(master), encoders)
            child_path = f'v{version}'
            self.putChild(unicode2bytes(child_path), child)
            if version == latest:
                self.putChild(b'latest', child)

    def render(self, request: server.Request) -> bytes:
        request.setHeader(b"content-type", JSON_ENCODED)
        min_vers = self.master.config.www.get('rest_minimum_version', 0)
        api_versions = dict(
            (f'v{v}', f'{self.base_url}api/v{v}') for v in self.version_classes if v > min_vers
        )
        data = json.dumps({"api_versions": api_versions})
        return unicode2bytes(data)


JSONRPC_CODES = {
    "parse_error": -32700,
    "invalid_request": -32600,
    "method_not_found": -32601,
    "invalid_params": -32602,
    "internal_error": -32603,
}


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
    def getEndpoint(
        self, request: server.Request, method: str, params: dict[str, Any]
    ) -> InlineCallbacksType[tuple[Endpoint, dict[str, Any]]]:
        # note that trailing slashes are not allowed
        assert request.postpath is not None
        request_postpath = tuple(bytes2unicode(p) for p in request.postpath)
        yield self.master.www.assertUserAllowed(request, request_postpath, method, params)
        ret = yield self.master.data.getEndpoint(request_postpath)
        return ret

    @contextmanager
    def handleErrors(self, writeError: Callable[[str | bytes, int, int], None]) -> Iterator[None]:
        try:
            yield
        except ConnectionDone:
            # Connection was cleanly closed
            pass
        except exceptions.InvalidPathError as e:
            msg = unicode2bytes(e.args[0])
            writeError(msg or b"invalid path", 404, JSONRPC_CODES['invalid_request'])
            return
        except exceptions.InvalidControlException as e:
            msg = unicode2bytes(str(e))
            writeError(msg or b"invalid control action", 501, JSONRPC_CODES["method_not_found"])
            return
        except exceptions.InvalidQueryParameter as e:
            msg = unicode2bytes(e.args[0])
            writeError(msg or b"invalid request", 400, JSONRPC_CODES["method_not_found"])
            return
        except BadJsonRpc2 as e:
            msg = unicode2bytes(e.message)
            writeError(msg, 400, e.jsonrpccode)
            return
        except Forbidden as e:
            # There is nothing in jsonrc spec about forbidden error, so pick
            # invalid request
            msg = unicode2bytes(e.message)
            writeError(msg, 403, JSONRPC_CODES["invalid_request"])
            return
        except Exception as e:
            log.err(_why='while handling API request')
            msg = unicode2bytes(repr(e))
            writeError(repr(e), 500, JSONRPC_CODES["internal_error"])
            return

    # JSONRPC2 support

    def decodeJsonRPC2(
        self, request: server.Request
    ) -> tuple[str, str | int | None, dict[str, Any]]:
        # Verify the content-type.  Browsers are easily convinced to send
        # POST data to arbitrary URLs via 'form' elements, but they won't
        # use the application/json content-type.
        if ContentTypeParser(request.getHeader(b'content-type')).gettype() != "application/json":
            raise BadJsonRpc2(
                'Invalid content-type (use application/json)', JSONRPC_CODES["invalid_request"]
            )

        try:
            assert request.content is not None
            data = json.loads(bytes2unicode(request.content.read()))
        except Exception as e:
            raise BadJsonRpc2(f"JSON parse error: {e!s}", JSONRPC_CODES["parse_error"]) from e

        if isinstance(data, list):
            raise BadJsonRpc2(
                "JSONRPC batch requests are not supported", JSONRPC_CODES["invalid_request"]
            )
        if not isinstance(data, dict):
            raise BadJsonRpc2(
                "JSONRPC root object must be an object", JSONRPC_CODES["invalid_request"]
            )

        def check(name, types, typename):
            if name not in data:
                raise BadJsonRpc2(f"missing key '{name}'", JSONRPC_CODES["invalid_request"])
            if not isinstance(data[name], types):
                raise BadJsonRpc2(f"'{name}' must be {typename}", JSONRPC_CODES["invalid_request"])

        check("jsonrpc", (str,), "a string")
        check("method", (str,), "a string")
        check("id", (str, int, type(None)), "a string, number, or null")
        check("params", (dict,), "an object")
        if data['jsonrpc'] != '2.0':
            raise BadJsonRpc2("only JSONRPC 2.0 is supported", JSONRPC_CODES['invalid_request'])
        return data["method"], data["id"], data['params']

    @defer.inlineCallbacks
    def renderJsonRpc(self, request: server.Request) -> InlineCallbacksType[None]:
        jsonRpcReply: dict[str, Any] = {'jsonrpc': "2.0"}

        def writeError(
            msg: str | bytes, errcode: int = 399, jsonrpccode: int = JSONRPC_CODES["internal_error"]
        ) -> None:
            if isinstance(msg, bytes):
                msg = bytes2unicode(msg)
            if self.debug:
                log.msg(f"JSONRPC error: {msg}")
            request.setResponseCode(errcode)
            request.setHeader(b'content-type', JSON_ENCODED)
            if "error" not in jsonRpcReply:  # already filled in by caller
                jsonRpcReply['error'] = {"code": jsonrpccode, "message": msg}
            data = json.dumps(jsonRpcReply)
            request.write(unicode2bytes(data))

        with self.handleErrors(writeError):
            method, id, params = self.decodeJsonRPC2(request)
            jsonRpcReply['id'] = id
            ep, kwargs = yield self.getEndpoint(request, method, params)
            userinfos = self.master.www.getUserInfos(request)
            if userinfos.get('anonymous'):
                owner = "anonymous"
            else:
                for field in ('email', 'username', 'full_name'):
                    owner = userinfos.get(field, None)
                    if owner:
                        break
            params['owner'] = owner

            result = yield ep.control(method, params, kwargs)
            jsonRpcReply['result'] = result

            data = json.dumps(jsonRpcReply, default=toJson, sort_keys=True, separators=(',', ':'))

            request.setHeader(b'content-type', JSON_ENCODED)
            if request.method == b"HEAD":
                request.setHeader(b"content-length", unicode2bytes(str(len(data))))
                request.write(b'')
            else:
                request.write(unicode2bytes(data))

    def decodeResultSpec(self, request: server.Request, endpoint: Endpoint) -> ResultSpec:
        args = request.args
        entityType = endpoint.rtype.entityType
        return self.master.data.resultspec_from_jsonapi(
            args, entityType, endpoint.kind == EndpointKind.COLLECTION
        )

    def _write_rest_error(
        self, request: server.Request, msg: str | bytes, errcode: int = 404
    ) -> None:
        if self.debug:
            log.msg(f"REST error: {msg!r}")
        request.setResponseCode(errcode)
        request.setHeader(b'content-type', b'text/plain; charset=utf-8')
        msg = bytes2unicode(msg)
        json_data = json.dumps({"error": msg})
        request.write(unicode2bytes(json_data))

    def _write_not_found_rest_error(
        self,
        request: server.Request,
        ep: Endpoint,
        rspec: ResultSpec,
        kwargs: dict[str, Any],
    ) -> None:
        self._write_rest_error(
            request=request,
            msg=(f"not found while getting from {ep!r} with arguments {rspec!r} and {kwargs!s}"),
        )

    async def _render_raw(
        self,
        request: server.Request,
        ep: Endpoint,
        rspec: ResultSpec,
        kwargs: dict[str, Any],
    ) -> None:
        assert ep.kind in (EndpointKind.RAW, EndpointKind.RAW_INLINE)

        is_stream_data = False
        try:
            data = await ep.stream(rspec, kwargs)
            is_stream_data = True
        except NotImplementedError:
            data = await ep.get(rspec, kwargs)

        if data is None:
            self._write_not_found_rest_error(request, ep, rspec=rspec, kwargs=kwargs)
            return

        request.setHeader(b"content-type", unicode2bytes(data['mime-type']) + b'; charset=utf-8')
        if ep.kind != EndpointKind.RAW_INLINE:
            request.setHeader(
                b"content-disposition", b'attachment; filename=' + unicode2bytes(data['filename'])
            )

        if not is_stream_data:
            request.write(unicode2bytes(data['raw']))
            return

        async for chunk in data['raw']:
            if _is_request_finished(request):
                return
            request.write(unicode2bytes(chunk))

    @defer.inlineCallbacks
    def renderRest(self, request: server.Request) -> InlineCallbacksType[None]:
        def writeError(
            msg: str | bytes, errcode: int = 404, jsonrpccode: int | None = None
        ) -> None:
            self._write_rest_error(request, msg=msg, errcode=errcode)

        with self.handleErrors(writeError):
            ep, kwargs = yield self.getEndpoint(request, bytes2unicode(request.method), {})

            rspec = self.decodeResultSpec(request, ep)
            if ep.kind in (EndpointKind.RAW, EndpointKind.RAW_INLINE):
                yield defer.Deferred.fromCoroutine(self._render_raw(request, ep, rspec, kwargs))
                return

            data = yield ep.get(rspec, kwargs)
            if data is None:
                self._write_not_found_rest_error(request, ep, rspec=rspec, kwargs=kwargs)
                return

            if _is_request_finished(request):
                return

            # post-process any remaining parts of the resultspec
            data = rspec.apply(data)

            # annotate the result with some metadata
            meta = {}
            if ep.kind == EndpointKind.COLLECTION:
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
            data = {typeName: data, 'meta': meta}

            # set up the content type and formatting options; if the request
            # accepts text/html or text/plain, the JSON will be rendered in a
            # readable, multiline format.

            if b'application/json' in (request.getHeader(b'accept') or b''):
                compact = True
                request.setHeader(b"content-type", b'application/json; charset=utf-8')
            else:
                compact = False
                request.setHeader(b"content-type", b'text/plain; charset=utf-8')

            # set up caching
            if self.cache_seconds:
                now = datetime.datetime.now(datetime.timezone.utc)
                expires = now + datetime.timedelta(seconds=self.cache_seconds)
                expiresBytes = unicode2bytes(expires.strftime("%a, %d %b %Y %H:%M:%S GMT"))
                request.setHeader(b"Expires", expiresBytes)
                request.setHeader(b"Pragma", b"no-cache")

            # filter out blanks if necessary and render the data
            encoder = json.encoder.JSONEncoder(default=toJson, sort_keys=True)
            if compact:
                encoder.item_separator, encoder.key_separator = (',', ':')
            else:
                encoder.indent = 2

            yield threads.deferToThread(V2RootResource._write_json_data, request, encoder, data)

    def reconfigResource(self, new_config: Any) -> None:
        # buildbotURL may contain reverse proxy path, Origin header is just
        # scheme + host + port
        buildbotURL = urlparse(unicode2bytes(new_config.buildbotURL))
        origin_self = buildbotURL.scheme + b"://" + buildbotURL.netloc
        # pre-translate the origin entries in the config
        self.origins = []
        for o in new_config.www.get('allowed_origins', [origin_self]):
            origin = bytes2unicode(o).lower()
            self.origins.append(re.compile(fnmatch.translate(origin)))

        # and copy some other flags
        self.debug = new_config.www.get('debug')
        self.cache_seconds = new_config.www.get('json_cache_seconds', 0)

    def render(self, request: server.Request) -> int:
        def writeError(msg: str | bytes, errcode: int = 400) -> None:
            msg = bytes2unicode(msg)
            if self.debug:
                log.msg(f"HTTP error: {msg}")
            request.setResponseCode(errcode)
            request.setHeader(b'content-type', b'text/plain; charset=utf-8')
            if request.method == b'POST':
                # jsonRPC callers want the error message in error.message
                data = json.dumps({"error": {"message": msg}})
                request.write(unicode2bytes(data))
            else:
                data = json.dumps({"error": msg})
                request.write(unicode2bytes(data))
            request.finish()

        return self.asyncRenderHelper(request, self.asyncRender, writeError)

    @defer.inlineCallbacks
    def asyncRender(self, request: server.Request) -> InlineCallbacksType[bytes | None]:
        # Handle CORS, if necessary.
        origins = self.origins
        if origins is not None:
            isPreflight = False
            reqOrigin = request.getHeader(b'origin')
            if reqOrigin:
                err = None
                reqOrigin = reqOrigin.lower()
                if not any(o.match(bytes2unicode(reqOrigin)) for o in self.origins):
                    err = b"invalid origin"
                elif request.method == b'OPTIONS':
                    preflightMethod = request.getHeader(b'access-control-request-method')
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
                request.setHeader(b"access-control-allow-headers", b"Content-Type")
                request.setHeader(b"access-control-max-age", b'3600')

                # if this was a preflight request, we're done
                if isPreflight:
                    return b""

        # based on the method, this is either JSONRPC or REST
        if request.method == b'POST':
            res = yield self.renderJsonRpc(request)
        elif request.method in (b'GET', b'HEAD'):
            res = yield self.renderRest(request)
        else:
            raise Error(400, b"invalid HTTP method")

        return res

    @staticmethod
    def _write_json_data(
        request: server.Request,
        encoder: json.encoder.JSONEncoder,
        data: Any,
    ) -> None:
        content_length = 0
        for chunk in encoder.iterencode(data):
            if _is_request_finished(request):
                return
            content_length += len(unicode2bytes(chunk))
        request.setHeader(b"content-length", unicode2bytes(str(content_length)))

        if request.method != b"HEAD":
            for chunk in encoder.iterencode(data):
                if _is_request_finished(request):
                    return
                request.write(unicode2bytes(chunk))


RestRootResource.addApiVersion(2, V2RootResource)
