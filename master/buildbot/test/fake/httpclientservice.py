# This file is part of Buildbot. Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members


import json as jsonmodule

from twisted.internet import defer
from twisted.logger import Logger
from twisted.python import deprecate
from twisted.python import versions
from zope.interface import implementer

from buildbot import util
from buildbot.interfaces import IHttpResponse
from buildbot.util import httpclientservice
from buildbot.util import service
from buildbot.util import toJson
from buildbot.util import unicode2bytes
from buildbot.util.twisted import async_to_deferred

log = Logger()


@implementer(IHttpResponse)
class ResponseWrapper:
    def __init__(self, code, content, url=None):
        self._content = content
        self._code = code
        self._url = url

    def content(self):
        content = unicode2bytes(self._content)
        return defer.succeed(content)

    def json(self):
        return defer.succeed(jsonmodule.loads(self._content))

    @property
    def code(self):
        return self._code

    @property
    def url(self):
        return self._url


class HTTPClientService(service.SharedService):
    """HTTPClientService is a SharedService class that fakes http requests for buildbot http
    service testing.

    This class is named the same as the real HTTPClientService so that it could replace the real
    class in tests. If a test creates this class earlier than the real one, fake is going to be
    used until the master is destroyed. Whenever a master wants to create real
    HTTPClientService, it will find an existing fake service with the same name and use it
    instead.
    """

    quiet = False

    def __init__(
        self, base_url, auth=None, headers=None, debug=False, verify=None, skipEncoding=False
    ):
        assert not base_url.endswith("/"), "baseurl should not end with /"
        super().__init__()
        self._session = httpclientservice.HTTPSession(
            self,
            base_url,
            auth=auth,
            headers=headers,
            debug=debug,
            verify=verify,
            skip_encoding=skipEncoding,
        )

        self._expected = []

    def updateHeaders(self, headers):
        self._session.update_headers(headers)

    @classmethod
    @async_to_deferred
    async def getService(cls, master, case, *args, **kwargs):
        def assertNotCalled(self, *_args, **_kwargs):
            case.fail(
                f"HTTPClientService called with *{_args!r}, **{_kwargs!r} "
                f"while should be called *{args!r} **{kwargs!r}"
            )

        case.patch(httpclientservice.HTTPClientService, "__init__", assertNotCalled)

        service = await super().getService(master, *args, **kwargs)
        service.case = case
        case.addCleanup(service.assertNoOutstanding)

        master.httpservice = service

        return service

    def expect(
        self,
        method,
        ep,
        session=None,
        params=None,
        headers=None,
        data=None,
        json=None,
        code=200,
        content=None,
        content_json=None,
        files=None,
        verify=None,
        cert=None,
        processing_delay_s=None,
    ):
        if content is not None and content_json is not None:
            return ValueError("content and content_json cannot be both specified")

        if content_json is not None:
            content = jsonmodule.dumps(content_json, default=toJson)

        self._expected.append({
            "method": method,
            "session": session,
            "ep": ep,
            "params": params,
            "headers": headers,
            "data": data,
            "json": json,
            "code": code,
            "content": content,
            "files": files,
            "verify": verify,
            "cert": cert,
            "processing_delay_s": processing_delay_s,
        })
        return None

    def assertNoOutstanding(self):
        self.case.assertEqual(
            0, len(self._expected), f"expected more http requests:\n {self._expected!r}"
        )

    @async_to_deferred
    async def _do_request(
        self,
        session,
        method,
        ep,
        params=None,
        headers=None,
        cookies=None,  # checks are not implemented
        data=None,
        json=None,
        files=None,
        auth=None,  # checks are not implemented
        timeout=None,
        verify=None,
        cert=None,
        allow_redirects=None,  # checks are not implemented
        proxies=None,  # checks are not implemented
    ) -> IHttpResponse:
        if ep.startswith('http://') or ep.startswith('https://'):
            pass
        else:
            assert ep == "" or ep.startswith("/"), "ep should start with /: " + ep

        if not self.quiet:
            log.debug(
                "{method} {ep} {params!r} <- {data!r}",
                method=method,
                ep=ep,
                params=params,
                data=data or json,
            )
        if json is not None:
            # ensure that the json is really jsonable
            jsonmodule.dumps(json, default=toJson)
        if files is not None:
            files = dict((k, v.read()) for (k, v) in files.items())
        if not self._expected:
            raise AssertionError(
                f"Not expecting a request, while we got: method={method!r}, ep={ep!r}, "
                f"params={params!r}, headers={headers!r}, data={data!r}, json={json!r}, "
                f"files={files!r}"
            )
        expect = self._expected.pop(0)
        processing_delay_s = expect.pop("processing_delay_s")

        expect_session = expect["session"] or self._session

        # pylint: disable=too-many-boolean-expressions
        if (
            expect_session.base_url != session.base_url
            or expect_session.auth != session.auth
            or expect_session.headers != session.headers
            or expect_session.verify != session.verify
            or expect_session.debug != session.debug
            or expect_session.skip_encoding != session.skip_encoding
            or expect["method"] != method
            or expect["ep"] != ep
            or expect["params"] != params
            or expect["headers"] != headers
            or expect["data"] != data
            or expect["json"] != json
            or expect["files"] != files
            or expect["verify"] != verify
            or expect["cert"] != cert
        ):
            raise AssertionError(
                "expecting:\n"
                f"session.base_url={expect_session.base_url!r}, "
                f"session.auth={expect_session.auth!r}, "
                f"session.headers={expect_session.headers!r}, "
                f"session.verify={expect_session.verify!r}, "
                f"session.debug={expect_session.debug!r}, "
                f"session.skip_encoding={expect_session.skip_encoding!r}, "
                f"method={expect['method']!r}, "
                f"ep={expect['ep']!r}, "
                f"params={expect['params']!r}, "
                f"headers={expect['headers']!r}, "
                f"data={expect['data']!r}, "
                f"json={expect['json']!r}, "
                f"files={expect['files']!r}, "
                f"verify={expect['verify']!r}, "
                f"cert={expect['cert']!r}"
                "\ngot      :\n"
                f"session.base_url={session.base_url!r}, "
                f"session.auth={session.auth!r}, "
                f"session.headers={session.headers!r}, "
                f"session.verify={session.verify!r}, "
                f"session.debug={session.debug!r}, "
                f"session.skip_encoding={session.skip_encoding!r}, "
                f"method={method!r}, "
                f"ep={ep!r}, "
                f"params={params!r}, "
                f"headers={headers!r}, "
                f"data={data!r}, "
                f"json={json!r}, "
                f"files={files!r}, "
                f"verify={verify!r}, "
                f"cert={cert!r}"
            )
        if not self.quiet:
            log.debug(
                "{method} {ep} -> {code} {content!r}",
                method=method,
                ep=ep,
                code=expect['code'],
                content=expect['content'],
            )

        if processing_delay_s is not None:
            await util.asyncSleep(1, reactor=self.master.reactor)

        return ResponseWrapper(expect['code'], expect['content'])

    # lets be nice to the auto completers, and don't generate that code
    @deprecate.deprecated(versions.Version("buildbot", 4, 1, 0))
    def get(self, ep, **kwargs):
        return self._do_request(self._session, 'get', ep, **kwargs)

    @deprecate.deprecated(versions.Version("buildbot", 4, 1, 0))
    def put(self, ep, **kwargs):
        return self._do_request(self._session, 'put', ep, **kwargs)

    @deprecate.deprecated(versions.Version("buildbot", 4, 1, 0))
    def delete(self, ep, **kwargs):
        return self._do_request(self._session, 'delete', ep, **kwargs)

    @deprecate.deprecated(versions.Version("buildbot", 4, 1, 0))
    def post(self, ep, **kwargs):
        return self._do_request(self._session, 'post', ep, **kwargs)
