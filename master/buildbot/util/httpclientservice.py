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
import textwrap

from twisted.internet import defer
from twisted.web.client import Agent
from twisted.web.client import HTTPConnectionPool
from zope.interface import implementer

from buildbot import config
from buildbot.interfaces import IHttpResponse
from buildbot.util import service
from buildbot.util import toJson
from buildbot.util import unicode2bytes
from buildbot.util.logger import Logger

try:
    import txrequests
except ImportError:
    txrequests = None

try:
    import treq
    implementer(IHttpResponse)(treq.response._Response)

except ImportError:
    treq = None

log = Logger()


@implementer(IHttpResponse)
class TxRequestsResponseWrapper(object):

    def __init__(self, res):
        self._res = res

    def content(self):
        return defer.succeed(self._res.content)

    def json(self):
        return defer.succeed(self._res.json())

    @property
    def code(self):
        return self._res.status_code


class HTTPClientService(service.SharedService):
    """A SharedService class that can make http requests to remote services.

    I can use either txrequests or treq, depending on what I find installed

    I provide minimal get/post/put/delete API with automatic baseurl joining, and json data encoding
    that is suitable for use from buildbot services.
    """
    TREQ_PROS_AND_CONS = textwrap.dedent("""
       txrequests is based on requests and is probably a bit more mature, but it requires threads to run,
       so has more overhead.
       treq is better integrated in twisted and is more and more feature equivalent

       txrequests is 2.8x slower than treq due to the use of threads.

       http://treq.readthedocs.io/en/latest/#feature-parity-w-requests
       pip install txrequests
           or
       pip install treq
    """)
    # Those could be in theory be overridden in master.cfg by using
    # import buildbot.util.httpclientservice.HTTPClientService.PREFER_TREQ = True
    # We prefer at the moment keeping it simple
    PREFER_TREQ = False
    MAX_THREADS = 5

    def __init__(self, base_url, auth=None, headers=None, verify=None, debug=False):
        assert not base_url.endswith(
            "/"), "baseurl should not end with /: " + base_url
        service.SharedService.__init__(self)
        self._base_url = base_url
        self._auth = auth
        self._headers = headers
        self._session = None
        self.verify = verify
        self.debug = debug

    def updateHeaders(self, headers):
        if self._headers is None:
            self._headers = {}
        self._headers.update(headers)

    @staticmethod
    def checkAvailable(from_module):
        """Call me at checkConfig time to properly report config error
           if neither txrequests or treq is installed
        """
        if txrequests is None and treq is None:
            config.error("neither txrequests nor treq is installed, but {} is requiring it\n\n{}".format(
                from_module, HTTPClientService.TREQ_PROS_AND_CONS))

    def startService(self):
        # treq only supports basicauth, so we force txrequests if the auth is
        # something else
        if self._auth is not None and not isinstance(self._auth, tuple):
            self.PREFER_TREQ = False
        if txrequests is not None and not self.PREFER_TREQ:
            self._session = txrequests.Session()
            self._doRequest = self._doTxRequest
        elif treq is None:
            raise ImportError("{classname} requires either txrequest or treq install."
                              " Users should call {classname}.checkAvailable() during checkConfig()"
                              " to properly alert the user.".format(classname=self.__class__.__name__))
        else:
            self._doRequest = self._doTReq
            self._pool = HTTPConnectionPool(self.master.reactor)
            self._pool.maxPersistentPerHost = self.MAX_THREADS
            self._agent = Agent(self.master.reactor, pool=self._pool)

    def stopService(self):
        if self._session:
            return self._session.close()
        return self._pool.closeCachedConnections()

    def _prepareRequest(self, ep, kwargs):
        assert ep == "" or ep.startswith("/"), "ep should start with /: " + ep
        url = self._base_url + ep
        if self._auth is not None and 'auth' not in kwargs:
            kwargs['auth'] = self._auth
        headers = kwargs.get('headers', {})
        if self._headers is not None:
            headers.update(self._headers)
        kwargs['headers'] = headers

        # we manually do the json encoding in order to automatically convert timestamps
        # for txrequests and treq
        json = kwargs.pop('json', None)
        if isinstance(json, dict):
            jsonStr = jsonmodule.dumps(json, default=toJson)
            jsonBytes = unicode2bytes(jsonStr)
            kwargs['headers']['Content-Type'] = 'application/json'
            kwargs['data'] = jsonBytes
        return url, kwargs

    def _doTxRequest(self, method, ep, **kwargs):
        url, kwargs = self._prepareRequest(ep, kwargs)
        if self.debug:
            log.debug("http {url} {kwargs}", url=url, kwargs=kwargs)

        def readContent(session, res):
            # this forces reading of the content inside the thread
            res.content
            if self.debug:
                log.debug("==> {code}: {content}", code=res.status_code, content=res.content)
            return res
        # read the whole content in the thread
        kwargs['background_callback'] = readContent
        if self.verify is False:
            kwargs['verify'] = False
        d = self._session.request(method, url, **kwargs)
        d.addCallback(TxRequestsResponseWrapper)
        d.addCallback(IHttpResponse)
        return d

    def _doTReq(self, method, ep, **kwargs):
        url, kwargs = self._prepareRequest(ep, kwargs)
        # treq requires header values to be an array
        kwargs['headers'] = dict([(k, [v])
                                  for k, v in kwargs['headers'].items()])
        kwargs['agent'] = self._agent

        d = getattr(treq, method)(url, **kwargs)
        d.addCallback(IHttpResponse)
        return d

    # lets be nice to the auto completers, and don't generate that code
    def get(self, ep, **kwargs):
        return self._doRequest('get', ep, **kwargs)

    def put(self, ep, **kwargs):
        return self._doRequest('put', ep, **kwargs)

    def delete(self, ep, **kwargs):
        return self._doRequest('delete', ep, **kwargs)

    def post(self, ep, **kwargs):
        return self._doRequest('post', ep, **kwargs)
