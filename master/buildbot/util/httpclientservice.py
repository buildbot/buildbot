# This file is part of Buildbot. Buildbot is free software: you can)
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
from twisted.python.threadpool import ThreadPool
from twisted.web.client import Agent
from twisted.web.client import HTTPConnectionPool
from zope.interface import implementer

from buildbot.interfaces import IHttpResponse
from buildbot.util import service
from buildbot.util import toJson
from buildbot.util import unicode2bytes

try:
    import txrequests
except ImportError:
    txrequests = None

import treq

log = Logger()


@implementer(IHttpResponse)
class TxRequestsResponseWrapper:
    def __init__(self, res):
        self._res = res

    def content(self):
        return defer.succeed(self._res.content)

    def json(self):
        return defer.succeed(self._res.json())

    @property
    def code(self):
        return self._res.status_code

    @property
    def url(self):
        return self._res.url


@implementer(IHttpResponse)
class TreqResponseWrapper:
    def __init__(self, res):
        self._res = res

    def content(self):
        return self._res.content()

    def json(self):
        return self._res.json()

    @property
    def code(self):
        return self._res.code

    @property
    def url(self):
        return self._res.request.absoluteURI.decode()


class HTTPClientService(service.SharedService):
    """A SharedService class that can make http requests to remote services.

    I provide minimal get/post/put/delete API with automatic baseurl joining, and json data encoding
    that is suitable for use from buildbot services.
    """

    # Those could be in theory be overridden in master.cfg by using
    # import buildbot.util.httpclientservice.HTTPClientService.PREFER_TREQ = True
    # We prefer at the moment keeping it simple
    PREFER_TREQ = False
    MAX_THREADS = 20

    def __init__(
        self,
        base_url,
        auth=None,
        headers=None,
        verify=None,
        cert=None,
        debug=False,
        skipEncoding=False,
    ):
        super().__init__()
        self._session = HTTPSession(
            self,
            base_url,
            auth=auth,
            headers=headers,
            verify=verify,
            cert=cert,
            debug=debug,
            skip_encoding=skipEncoding,
        )
        self._pool = None
        self._txrequests_sessions = []

    def updateHeaders(self, headers):
        self._session.update_headers(headers)

    @staticmethod
    @deprecate.deprecated(versions.Version("buildbot", 4, 1, 0))
    def checkAvailable(from_module):
        pass

    def startService(self):
        if txrequests is not None:
            self._txrequests_pool = ThreadPool(minthreads=1, maxthreads=self.MAX_THREADS)
            # unclosed ThreadPool leads to reactor hangs at shutdown
            # this is a problem in many situation, so better enforce pool stop here
            self.master.reactor.addSystemEventTrigger(
                "after",
                "shutdown",
                lambda: self._txrequests_pool.stop() if self._txrequests_pool.started else None,
            )
            self._txrequests_pool.start()

        self._pool = HTTPConnectionPool(self.master.reactor)
        self._pool.maxPersistentPerHost = self.MAX_THREADS
        return super().startService()

    @defer.inlineCallbacks
    def stopService(self):
        if txrequests is not None:
            sessions = self._txrequests_sessions
            self._txrequests_sessions = []
            for session in sessions:
                session.close()
            self._txrequests_pool.stop()
        if self._pool:
            yield self._pool.closeCachedConnections()
        yield super().stopService()

    def _do_request(self, session, method, ep, **kwargs):
        prefer_treq = self.PREFER_TREQ
        if session.auth is not None and not isinstance(session.auth, tuple):
            prefer_treq = False
        if prefer_treq or txrequests is None:
            return self._do_treq(session, method, ep, **kwargs)
        else:
            return self._do_txrequest(session, method, ep, **kwargs)

    def _prepare_request(self, session, ep, kwargs):
        if ep.startswith('http://') or ep.startswith('https://'):
            url = ep
        else:
            assert ep == "" or ep.startswith("/"), "ep should start with /: " + ep
            url = session.base_url + ep
        if session.auth is not None and 'auth' not in kwargs:
            kwargs['auth'] = session.auth
        headers = kwargs.get('headers', {})
        if session.headers is not None:
            headers.update(session.headers)
        kwargs['headers'] = headers

        # we manually do the json encoding in order to automatically convert timestamps
        # for txrequests and treq
        json = kwargs.pop('json', None)
        if isinstance(json, (dict, list)):
            jsonStr = jsonmodule.dumps(json, default=toJson)
            kwargs['headers']['Content-Type'] = 'application/json'
            if session.skip_encoding:
                kwargs['data'] = jsonStr
            else:
                jsonBytes = unicode2bytes(jsonStr)
                kwargs['data'] = jsonBytes
        return url, kwargs

    @defer.inlineCallbacks
    def _do_txrequest(self, session, method, ep, **kwargs):
        url, kwargs = yield self._prepare_request(session, ep, kwargs)
        if session.debug:
            log.debug("http {url} {kwargs}", url=url, kwargs=kwargs)

        def readContent(txrequests_session, res):
            # this forces reading of the content inside the thread
            _ = res.content
            if session.debug:
                log.debug("==> {code}: {content}", code=res.status_code, content=res.content)
            return res

        # read the whole content in the thread
        kwargs['background_callback'] = readContent
        if session.verify is False:
            kwargs['verify'] = False
        elif session.verify:
            kwargs['verify'] = session.verify

        if session.cert:
            kwargs['cert'] = session.cert
        if session._txrequests_session is None:
            session._txrequests_session = txrequests.Session(
                pool=self._txrequests_pool, maxthreads=self.MAX_THREADS
            )
            # FIXME: remove items from the list as HTTPSession objects are destroyed
            self._txrequests_sessions.append(session._txrequests_session)

        res = yield session._txrequests_session.request(method, url, **kwargs)
        return IHttpResponse(TxRequestsResponseWrapper(res))

    @defer.inlineCallbacks
    def _do_treq(self, session, method, ep, **kwargs):
        url, kwargs = yield self._prepare_request(session, ep, kwargs)
        # treq requires header values to be an array
        if "headers" in kwargs:
            kwargs['headers'] = {k: [v] for k, v in kwargs["headers"].items()}

        if session._treq_agent is None:
            session._trex_agent = Agent(self.master.reactor, pool=self._pool)
        kwargs['agent'] = session._trex_agent

        res = yield getattr(treq, method)(url, **kwargs)
        return IHttpResponse(TreqResponseWrapper(res))

    @deprecate.deprecated(versions.Version("buildbot", 4, 1, 0), "Use HTTPSession.get()")
    def get(self, ep, **kwargs):
        return self._do_request(self._session, 'get', ep, **kwargs)

    @deprecate.deprecated(versions.Version("buildbot", 4, 1, 0), "Use HTTPSession.put()")
    def put(self, ep, **kwargs):
        return self._do_request(self._session, 'put', ep, **kwargs)

    @deprecate.deprecated(versions.Version("buildbot", 4, 1, 0), "Use HTTPSession.delete()")
    def delete(self, ep, **kwargs):
        return self._do_request(self._session, 'delete', ep, **kwargs)

    @deprecate.deprecated(versions.Version("buildbot", 4, 1, 0), "Use HTTPSession.post()")
    def post(self, ep, **kwargs):
        return self._do_request(self._session, 'post', ep, **kwargs)


class HTTPSession:
    def __init__(
        self,
        http,
        base_url,
        auth=None,
        headers=None,
        verify=None,
        cert=None,
        debug=False,
        skip_encoding=False,
    ):
        assert not base_url.endswith("/"), "baseurl should not end with /: " + base_url
        self.http = http
        self.base_url = base_url
        self.auth = auth
        self.headers = headers
        self.pool = None
        self.verify = verify
        self.cert = cert
        self.debug = debug
        self.skip_encoding = skip_encoding

        self._treq_agent = None
        self._txrequests_session = None

    def update_headers(self, headers):
        if self.headers is None:
            self.headers = {}
        self.headers.update(headers)

    def get(self, ep, **kwargs):
        return self.http._do_request(self, 'get', ep, **kwargs)

    def put(self, ep, **kwargs):
        return self.http._do_request(self, 'put', ep, **kwargs)

    def delete(self, ep, **kwargs):
        return self.http._do_request(self, 'delete', ep, **kwargs)

    def post(self, ep, **kwargs):
        return self.http._do_request(self, 'post', ep, **kwargs)
