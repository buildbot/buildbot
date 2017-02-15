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
from future.utils import iteritems

from twisted.internet import defer
from twisted.internet import reactor

from buildbot import config
from buildbot.process.buildstep import FAILURE
from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import BuildStep

# use the 'requests' lib: http://python-requests.org
try:
    import txrequests
    import requests
except ImportError:
    txrequests = None


# This step uses a global Session object, which encapsulates a thread pool as
# well as state such as cookies and authentication.  This state may pose
# problems for users, where one step may get a cookie that is subsequently used
# by another step in a different build.

_session = None


def getSession():
    global _session
    if _session is None:
        _session = txrequests.Session()
        reactor.addSystemEventTrigger("before", "shutdown", closeSession)
    return _session


def setSession(session):
    global _session
    _session = session


def closeSession():
    global _session
    if _session is not None:
        _session.close()
        _session = None


class HTTPStep(BuildStep):

    name = 'HTTPStep'
    description = 'Requesting'
    descriptionDone = 'Requested'
    requestsParams = ["params", "data", "json", "headers",
                      "cookies", "files", "auth",
                      "timeout", "allow_redirects", "proxies",
                      "hooks", "stream", "verify", "cert"]
    renderables = requestsParams + ["method", "url"]
    session = None

    def __init__(self, url, method, **kwargs):
        if txrequests is None:
            config.error(
                "Need to install txrequest to use this step:\n\n pip install txrequests")

        if method not in ('POST', 'GET', 'PUT', 'DELETE', 'HEAD', 'OPTIONS'):
            config.error("Wrong method given: '%s' is not known" % method)

        self.method = method
        self.url = url

        for param in HTTPStep.requestsParams:
            setattr(self, param, kwargs.pop(param, None))

        BuildStep.__init__(self, **kwargs)

    def start(self):
        d = self.doRequest()
        d.addErrback(self.failed)

    @defer.inlineCallbacks
    def doRequest(self):
        # create a new session if it doesn't exist
        self.session = getSession()

        requestkwargs = {
            'method': self.method,
            'url': self.url
        }

        for param in self.requestsParams:
            value = getattr(self, param, None)
            if value is not None:
                requestkwargs[param] = value

        log = self.addLog('log')

        # known methods already tested in __init__

        log.addHeader('Performing %s request to %s\n' %
                      (self.method, self.url))
        if self.params:
            log.addHeader('Parameters:\n')
            params = requestkwargs.get("params", {})
            if params:
                params = sorted(iteritems(params), key=lambda x: x[0])
                requestkwargs['params'] = params
            for k, v in params:
                log.addHeader('\t%s: %s\n' % (k, v))
        data = requestkwargs.get("data", None)
        if data:
            log.addHeader('Data:\n')
            if isinstance(data, dict):
                for k, v in iteritems(data):
                    log.addHeader('\t%s: %s\n' % (k, v))
            else:
                log.addHeader('\t%s\n' % data)

        try:
            r = yield self.session.request(**requestkwargs)
        except requests.exceptions.ConnectionError as e:
            log.addStderr(
                'An exception occured while performing the request: %s' % e)
            self.finished(FAILURE)
            return

        if r.history:
            log.addStdout('\nRedirected %d times:\n\n' % len(r.history))
            for rr in r.history:
                self.log_response(rr)
                log.addStdout('=' * 60 + '\n')

        self.log_response(r)

        log.finish()

        self.descriptionDone = ["Status code: %d" % r.status_code]
        if (r.status_code < 400):
            self.finished(SUCCESS)
        else:
            self.finished(FAILURE)

    def log_response(self, response):
        log = self.getLog('log')

        log.addHeader('Request Header:\n')
        for k, v in iteritems(response.request.headers):
            log.addHeader('\t%s: %s\n' % (k, v))

        log.addStdout('URL: %s\n' % response.url)

        if response.status_code == requests.codes.ok:
            log.addStdout('Status: %s\n' % response.status_code)
        else:
            log.addStderr('Status: %s\n' % response.status_code)

        log.addHeader('Response Header:\n')
        for k, v in iteritems(response.headers):
            log.addHeader('\t%s: %s\n' % (k, v))

        log.addStdout(' ------ Content ------\n%s' % response.text)
        self.addLog('content').addStdout(response.text)


class POST(HTTPStep):

    def __init__(self, url, **kwargs):
        HTTPStep.__init__(self, url, method='POST', **kwargs)


class GET(HTTPStep):

    def __init__(self, url, **kwargs):
        HTTPStep.__init__(self, url, method='GET', **kwargs)


class PUT(HTTPStep):

    def __init__(self, url, **kwargs):
        HTTPStep.__init__(self, url, method='PUT', **kwargs)


class DELETE(HTTPStep):

    def __init__(self, url, **kwargs):
        HTTPStep.__init__(self, url, method='DELETE', **kwargs)


class HEAD(HTTPStep):

    def __init__(self, url, **kwargs):
        HTTPStep.__init__(self, url, method='HEAD', **kwargs)


class OPTIONS(HTTPStep):

    def __init__(self, url, **kwargs):
        HTTPStep.__init__(self, url, method='OPTIONS', **kwargs)
