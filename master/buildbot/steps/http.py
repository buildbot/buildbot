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

from twisted.internet import defer

from buildbot import config
from buildbot.process.buildstep import FAILURE
from buildbot.process.buildstep import SUCCESS
from buildbot.process.buildstep import BuildStep
from buildbot.steps.http_oldstyle import DELETE
from buildbot.steps.http_oldstyle import GET
from buildbot.steps.http_oldstyle import HEAD
from buildbot.steps.http_oldstyle import OPTIONS
from buildbot.steps.http_oldstyle import POST
from buildbot.steps.http_oldstyle import PUT
from buildbot.steps.http_oldstyle import HTTPStep
from buildbot.steps.http_oldstyle import closeSession
from buildbot.steps.http_oldstyle import getSession
from buildbot.steps.http_oldstyle import setSession

# use the 'requests' lib: https://requests.readthedocs.io/en/master/
try:
    import txrequests
    import requests
except ImportError:
    txrequests = None

_hush_pyflakes = [
    DELETE,
    GET,
    HEAD,
    HTTPStep,
    OPTIONS,
    POST,
    PUT,
    closeSession,
    getSession,
    setSession,
]
del _hush_pyflakes

# TODO: move session singleton handling back to this module from http_oldstyle


def _headerSet(headers):
    return frozenset(map(lambda x: x.casefold(), headers))


class HTTPStepNewStyle(BuildStep):

    name = 'HTTPStep'
    description = 'Requesting'
    descriptionDone = 'Requested'
    requestsParams = ["params", "data", "json", "headers",
                      "cookies", "files", "auth",
                      "timeout", "allow_redirects", "proxies",
                      "hooks", "stream", "verify", "cert"]
    renderables = requestsParams + ["method", "url"]
    session = None

    def __init__(self, url, method,
                 hide_request_headers=None, hide_response_headers=None,
                 **kwargs):
        if txrequests is None:
            config.error(
                "Need to install txrequest to use this step:\n\n pip install txrequests")

        if method not in ('POST', 'GET', 'PUT', 'DELETE', 'HEAD', 'OPTIONS'):
            config.error("Wrong method given: '{}' is not known".format(method))

        self.method = method
        self.url = url

        self.hide_request_headers = _headerSet(hide_request_headers or [])
        self.hide_response_headers = _headerSet(hide_response_headers or [])

        for param in self.requestsParams:
            setattr(self, param, kwargs.pop(param, None))

        super().__init__(**kwargs)

    @defer.inlineCallbacks
    def run(self):
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

        log = yield self.addLog('log')

        # known methods already tested in __init__

        yield log.addHeader('Performing {} request to {}\n'.format(self.method, self.url))
        if self.params:
            yield log.addHeader('Parameters:\n')
            params = sorted(self.params.items(), key=lambda x: x[0])
            requestkwargs['params'] = params
            for k, v in params:
                yield log.addHeader('\t{}: {}\n'.format(k, v))
        data = requestkwargs.get("data", None)
        if data:
            yield log.addHeader('Data:\n')
            if isinstance(data, dict):
                for k, v in data.items():
                    yield log.addHeader('\t{}: {}\n'.format(k, v))
            else:
                yield log.addHeader('\t{}\n'.format(data))

        try:
            r = yield self.session.request(**requestkwargs)
        except requests.exceptions.ConnectionError as e:
            yield log.addStderr('An exception occurred while performing the request: {}'.format(e))
            return FAILURE

        if r.history:
            yield log.addStdout('\nRedirected %d times:\n\n' % len(r.history))
            for rr in r.history:
                yield self.log_response(log, rr)
                yield log.addStdout('=' * 60 + '\n')

        yield self.log_response(log, r)

        yield log.finish()

        self.descriptionDone = ["Status code: %d" % r.status_code]
        if (r.status_code < 400):
            return SUCCESS
        else:
            return FAILURE

    @defer.inlineCallbacks
    def log_response(self, log, response):

        yield log.addHeader('Request Headers:\n')
        for k, v in response.request.headers.items():
            if k.casefold() in self.hide_request_headers:
                v = '<HIDDEN>'
            yield log.addHeader('\t{}: {}\n'.format(k, v))

        yield log.addStdout('URL: {}\n'.format(response.url))

        if response.status_code == requests.codes.ok:
            yield log.addStdout('Status: {}\n'.format(response.status_code))
        else:
            yield log.addStderr('Status: {}\n'.format(response.status_code))

        yield log.addHeader('Response Headers:\n')
        for k, v in response.headers.items():
            if k.casefold() in self.hide_response_headers:
                v = '<HIDDEN>'
            yield log.addHeader('\t{}: {}\n'.format(k, v))

        yield log.addStdout(' ------ Content ------\n{}'.format(response.text))
        content_log = yield self.addLog('content')
        yield content_log.addStdout(response.text)


class POSTNewStyle(HTTPStepNewStyle):

    def __init__(self, url, **kwargs):
        super().__init__(url, method='POST', **kwargs)


class GETNewStyle(HTTPStepNewStyle):

    def __init__(self, url, **kwargs):
        super().__init__(url, method='GET', **kwargs)


class PUTNewStyle(HTTPStepNewStyle):

    def __init__(self, url, **kwargs):
        super().__init__(url, method='PUT', **kwargs)


class DELETENewStyle(HTTPStepNewStyle):

    def __init__(self, url, **kwargs):
        super().__init__(url, method='DELETE', **kwargs)


class HEADNewStyle(HTTPStepNewStyle):

    def __init__(self, url, **kwargs):
        super().__init__(url, method='HEAD', **kwargs)


class OPTIONSNewStyle(HTTPStepNewStyle):

    def __init__(self, url, **kwargs):
        super().__init__(url, method='OPTIONS', **kwargs)
