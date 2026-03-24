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
import os
from importlib.metadata import entry_points
from io import BytesIO
from io import StringIO
from typing import TYPE_CHECKING
from typing import Any
from unittest import mock
from urllib.parse import parse_qs
from urllib.parse import unquote as urlunquote
from uuid import uuid1

from twisted.internet import defer
from twisted.web import server

from buildbot.test.fake import fakemaster
from buildbot.util import bytes2unicode
from buildbot.util import unicode2bytes
from buildbot.util.importlib_compat import entry_points_get
from buildbot.www import auth
from buildbot.www import authz
from buildbot.www.authz.authz import Authz

if TYPE_CHECKING:
    from twisted.trial import unittest

    from buildbot.util.twisted import InlineCallbacksType

    _WwwTestMixinBase = unittest.TestCase
else:
    _WwwTestMixinBase = object


class FakeSession:
    def __init__(self) -> None:
        self.user_info: dict[str, Any] = {"anonymous": True}

    def updateSession(self, request: Any) -> None:
        pass


class FakeRequest:
    written = b''
    finished = False
    redirected_to: bytes | None = None
    rendered_resource: Any = None
    failure: Any = None
    method = b'GET'
    path = b'/req.path'
    responseCode = 200

    session: Any = None
    content: Any = None

    def __init__(self, path: bytes | None = None) -> None:
        # from twisted.web.http.Request. Used to detect connection dropped
        self.channel: Any = True

        self.headers: dict[bytes, list[bytes]] = {}
        self.input_headers: dict[bytes, bytes] = {}
        self.prepath: list[bytes] = []
        assert path is not None
        x = path.split(b'?', 1)
        if len(x) == 1:
            self.path = path
            self.args: dict[bytes, Any] = {}
        else:
            path, argstring = x
            self.path = path
            self.args = parse_qs(argstring, 1)  # type: ignore[arg-type]
        self.uri = self.path
        self.postpath: list[bytes] = []
        for p in path[1:].split(b'/'):
            decoded_path = urlunquote(bytes2unicode(p))
            self.postpath.append(unicode2bytes(decoded_path))

        self.deferred: defer.Deferred[Any] = defer.Deferred()

    def write(self, data: bytes) -> None:
        self.written = self.written + data

    def redirect(self, url: bytes) -> None:
        self.redirected_to = url

    def render(self, rsrc: Any) -> None:
        rendered_resource = rsrc
        self.deferred.callback(rendered_resource)

    def finish(self) -> None:
        self.finished = True
        if self.redirected_to is not None:
            self.deferred.callback({"redirected": self.redirected_to})
        else:
            self.deferred.callback(self.written)

    def setResponseCode(self, code: int, text: bytes | None = None) -> None:
        # twisted > 16 started to assert this
        assert isinstance(code, int)
        self.responseCode = code
        self.responseText = text

    def setHeader(self, hdr: bytes, value: bytes) -> None:
        assert isinstance(hdr, bytes)
        assert isinstance(value, bytes)
        self.headers.setdefault(hdr, []).append(value)

    def getHeader(self, key: bytes) -> bytes | None:
        assert isinstance(key, bytes)
        return self.input_headers.get(key)

    def processingFailed(self, f: Any) -> None:
        self.deferred.errback(f)

    def notifyFinish(self) -> defer.Deferred[Any]:
        d: defer.Deferred[Any] = defer.Deferred()

        @self.deferred.addBoth
        def finished(res: Any) -> Any:
            d.callback(res)
            return res

        return d

    def getSession(self) -> Any:
        return self.session


class RequiresWwwMixin:
    # mix this into a TestCase to skip if buildbot-www is not installed

    if not [ep for ep in entry_points_get(entry_points(), 'buildbot.www') if ep.name == 'base']:
        if 'BUILDBOT_TEST_REQUIRE_WWW' in os.environ:
            raise RuntimeError(
                '$BUILDBOT_TEST_REQUIRE_WWW is set but buildbot-www is not installed'
            )
        skip = 'buildbot-www not installed'


class WwwTestMixin(RequiresWwwMixin, _WwwTestMixinBase):
    UUID = str(uuid1())
    request: FakeRequest

    @defer.inlineCallbacks
    def make_master(
        self, wantGraphql: bool = False, url: str | None = None, **kwargs: Any
    ) -> InlineCallbacksType[fakemaster.FakeMaster]:
        master = yield fakemaster.make_master(self, wantData=True, wantGraphql=wantGraphql)
        self.master = master
        master.www = mock.Mock()  # to handle the resourceNeedsReconfigs call
        master.www.getUserInfos = lambda _: getattr(
            self.master.session, "user_info", {"anonymous": True}
        )
        cfg: dict[str, Any] = {"port": None, "auth": auth.NoAuth(), "authz": authz.Authz()}
        cfg.update(kwargs)
        master.config.www = cfg
        if url is not None:
            master.config.buildbotURL = url
        self.master.session = FakeSession()
        self.master.authz = cfg["authz"]
        assert isinstance(self.master.authz, Authz)
        self.master.authz.setMaster(self.master)
        return master

    def make_request(self, path: bytes | None = None, method: bytes = b'GET') -> FakeRequest:
        self.request = FakeRequest(path)
        self.request.session = self.master.session
        self.request.method = method
        return self.request

    def render_resource(
        self,
        rsrc: Any,
        path: bytes = b'/',
        accept: bytes | None = None,
        method: bytes = b'GET',
        origin: bytes | None = None,
        access_control_request_method: bytes | None = None,
        extraHeaders: dict[bytes, bytes] | None = None,
        request: FakeRequest | None = None,
        content: bytes | None = None,
        content_type: bytes | None = None,
    ) -> defer.Deferred[Any]:
        if not request:
            request = self.make_request(path, method=method)
            if accept:
                request.input_headers[b'accept'] = accept
            if origin:
                request.input_headers[b'origin'] = origin
            if access_control_request_method:
                request.input_headers[b'access-control-request-method'] = (
                    access_control_request_method
                )
            if extraHeaders is not None:
                request.input_headers.update(extraHeaders)
            if content_type is not None:
                request.input_headers.update({b'content-type': content_type})
                request.content = BytesIO(content)  # type: ignore[arg-type]

        rv = rsrc.render(request)
        if rv != server.NOT_DONE_YET:
            if rv is not None:
                request.write(rv)
            request.finish()
        return request.deferred

    @defer.inlineCallbacks
    def render_control_resource(
        self,
        rsrc: Any,
        path: bytes = b'/',
        params: dict[str, Any] | None = None,
        requestJson: str | None = None,
        action: str = "notfound",
        id: int | str | None = None,
        content_type: bytes | str = b'application/json',
    ) -> InlineCallbacksType[None]:
        # pass *either* a request or postpath
        if params is None:
            params = {}
        id = id or self.UUID
        request = self.make_request(path)
        request.method = b"POST"
        request.content = StringIO(
            requestJson
            or json.dumps({"jsonrpc": "2.0", "method": action, "params": params, "id": id})
        )
        request.input_headers = {b'content-type': content_type}  # type: ignore[dict-item]
        rv = rsrc.render(request)
        if rv == server.NOT_DONE_YET:
            rv = yield request.deferred

        res = json.loads(bytes2unicode(rv))
        self.assertIn("jsonrpc", res)
        self.assertEqual(res["jsonrpc"], "2.0")
        if not requestJson:
            # requestJson is used for invalid requests, so don't expect ID
            self.assertIn("id", res)
            self.assertEqual(res["id"], id)

    def assertRequest(
        self,
        content: bytes | None = None,
        contentJson: Any = None,
        contentType: bytes | None = None,
        responseCode: int | None = None,
        contentDisposition: Any = None,
        headers: dict[bytes, list[bytes]] | None = None,
    ) -> None:
        if headers is None:
            headers = {}
        got: dict[Any, Any] = {}
        exp: dict[Any, Any] = {}
        if content is not None:
            got['content'] = self.request.written
            exp['content'] = content
        if contentJson is not None:
            got['contentJson'] = json.loads(bytes2unicode(self.request.written))
            exp['contentJson'] = contentJson
        if contentType is not None:
            got['contentType'] = self.request.headers[b'content-type']
            exp['contentType'] = [contentType]
        if responseCode is not None:
            got['responseCode'] = str(self.request.responseCode)
            exp['responseCode'] = str(responseCode)
        for header, value in headers.items():
            got[header] = self.request.headers.get(header)
            exp[header] = value
        self.assertEqual(got, exp)
