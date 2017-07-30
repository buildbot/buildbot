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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import json as jsonmodule

import mock

from twisted.internet import defer
from zope.interface import implementer

from buildbot.interfaces import IHttpResponse
from buildbot.util import httpclientservice
from buildbot.util import service
from buildbot.util import toJson
from buildbot.util import unicode2bytes
from buildbot.util.logger import Logger

log = Logger()


@implementer(IHttpResponse)
class ResponseWrapper(object):

    def __init__(self, code, content):
        self._content = content
        self._code = code

    def content(self):
        content = unicode2bytes(self._content)
        return defer.succeed(content)

    def json(self):
        return defer.succeed(jsonmodule.loads(self._content))

    @property
    def code(self):
        return self._code


class HTTPClientService(service.SharedService):
    """A SharedService class that fakes http requests for buildbot http service testing.

    It is called HTTPClientService so that it substitute the real HTTPClientService
    if created earlier in the test.

    getName from the fake and getName from the real must return the same values.
    """
    quiet = False

    def __init__(self, base_url, auth=None, headers=None, debug=None, verify=None):
        assert not base_url.endswith("/"), "baseurl should not end with /"
        service.SharedService.__init__(self)
        self._base_url = base_url
        self._auth = auth

        self._headers = headers
        self._session = None
        self._expected = []

    def updateHeaders(self, headers):
        if self._headers is None:
            self._headers = {}
        self._headers.update(headers)

    @classmethod
    def getFakeService(cls, master, case, *args, **kwargs):
        ret = cls.getService(master, *args, **kwargs)

        def assertNotCalled(self, *_args, **_kwargs):
            case.fail(("HTTPClientService called with *{!r}, **{!r}"
                       "while should be called *{!r} **{!r}").format(
                _args, _kwargs, args, kwargs))
        case.patch(httpclientservice.HTTPClientService, "__init__", assertNotCalled)

        @ret.addCallback
        def assertNoOutstanding(fake):
            fake.case = case
            case.addCleanup(fake.assertNoOutstanding)
            return fake
        return ret
    # tests should ensure this has been called
    checkAvailable = mock.Mock()

    def expect(self, method, ep, params=None, data=None, json=None, code=200,
               content=None, content_json=None):
        if content is not None and content_json is not None:
            return ValueError("content and content_json cannot be both specified")

        if content_json is not None:
            content = jsonmodule.dumps(content_json, default=toJson)

        self._expected.append(dict(
            method=method, ep=ep, params=params, data=data, json=json, code=code,
            content=content))

    def assertNoOutstanding(self):
        self.case.assertEqual(0, len(self._expected),
                              "expected more http requests:\n {!r}".format(self._expected))

    def _doRequest(self, method, ep, params=None, data=None, json=None):
        assert ep == "" or ep.startswith("/"), "ep should start with /: " + ep
        if not self.quiet:
            log.debug("{method} {ep} {params!r} <- {data!r}",
                      method=method, ep=ep, params=params, data=data or json)
        if json is not None:
            # ensure that the json is really jsonable
            jsonmodule.dumps(json, default=toJson)
        if not self._expected:
            raise AssertionError(
                "Not expecting a request, while we got: "
                "method={!r}, ep={!r}, params={!r}, data={!r}, json={!r}".format(
                    method, ep, params, data, json))
        expect = self._expected.pop(0)
        if (expect['method'] != method or expect['ep'] != ep or expect['params'] != params or
                expect['data'] != data or expect['json'] != json):
            raise AssertionError(
                "expecting:\n"
                "method={!r}, ep={!r}, params={!r}, data={!r}, json={!r}\n"
                "got      :\n"
                "method={!r}, ep={!r}, params={!r}, data={!r}, json={!r}".format(
                    expect['method'], expect['ep'], expect['params'], expect['data'], expect['json'],
                    method, ep, params, data, json,
                ))
        if not self.quiet:
            log.debug("{method} {ep} -> {code} {content!r}",
                      method=method, ep=ep, code=expect['code'], content=expect['content'])
        return defer.succeed(ResponseWrapper(expect['code'], expect['content']))

    # lets be nice to the auto completers, and don't generate that code
    def get(self, ep, **kwargs):
        return self._doRequest('get', ep, **kwargs)

    def put(self, ep, **kwargs):
        return self._doRequest('put', ep, **kwargs)

    def delete(self, ep, **kwargs):
        return self._doRequest('delete', ep, **kwargs)

    def post(self, ep, **kwargs):
        return self._doRequest('post', ep, **kwargs)
