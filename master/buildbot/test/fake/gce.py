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

from buildbot.util import gceclientservice


class GCEAsyncResult:
    def __init__(self, record_id):
        self.record_id = record_id


class ExpectedRequest:
    NORMAL = 1
    UNTIL = 2

    def __init__(self, mode, httpMethod, url, params={}, json={}, result={}, data=None, resultCode=200):
        self.mode = mode
        self.httpMethod = httpMethod
        self.url = url
        self.params = params
        self.json = json
        self.data = data
        self.result = result
        self.resultCode = resultCode


class GCERecorder(gceclientservice.GCEClientService):
    IGNORE = object()

    def __init__(self, scopes, sa_credentials, project=None, zone=None, instance=None, renderer=None):
        self.expectations = []
        self.record_id = 0
        self.record = []
        self.inFlight = {}
        self.asyncId = 0

        gceclientservice.GCEClientService.__init__(
            self, scopes, sa_credentials, project=project, zone=zone, instance=instance,
            renderer=renderer)

        self._doRequest = self.interceptRequest

    def expect(self, method, url, params={}, json={}, data=None, result={}, resultCode=200):
        self.expectations.append(ExpectedRequest(
            ExpectedRequest.NORMAL, method, url, params=params, json=json, data=data,
            result=result, resultCode=resultCode))

    def expectOperationRequest(self, method, url, params={}, json={}, data=None, resultCode=200):
        self.asyncId += 1
        selfLink = 'async-{}'.format(self.asyncId)
        self.expectations.append(ExpectedRequest(
            ExpectedRequest.NORMAL, method, url, params=params, json=json, data=data,
            result={'selfLink': selfLink, 'status': 'STARTED'},
            resultCode=resultCode))
        return selfLink

    def expectWaitForOperation(self, selfLink, status='DONE'):
        self.expectations.append(ExpectedRequest(
            ExpectedRequest.NORMAL, 'GET', selfLink,
            result={'status': 'DONE'}, resultCode=200))

    def expectInstanceStateWait(self, targetState):
        return self.expect(
            'GET', '/compute/v1/projects/p/zones/z/instances/i',
            params={'fields': 'status'},
            result={'status': targetState})

    def ignoreUntil(self, method, url):
        self.expectations.append(ExpectedRequest(
            ExpectedRequest.UNTIL, method, url))

    def validateIsExpected(self, method, url, params, json, data):
        if not self.expectations:
            msg = "got {} {} but was not expecting any request".format(method, url)
            assert False, msg

        request = self.expectations[0]
        methodMatches = request.httpMethod == method
        urlMatches = request.url == GCERecorder.IGNORE or request.url == url
        paramsMatches = request.params == GCERecorder.IGNORE or request.params == params
        jsonMatches = request.json == GCERecorder.IGNORE or request.json == json
        dataMatches = request.data == GCERecorder.IGNORE or request.data == data
        matches = (methodMatches and urlMatches and paramsMatches and jsonMatches and dataMatches)

        if request.mode == ExpectedRequest.NORMAL:
            if matches:
                self.expectations.pop(0)
                return request

            assert (methodMatches and urlMatches), "expected {} {}, got {} {}".format(
                request.httpMethod, request.url, method, url)
            assert paramsMatches, "expected {} {} to have parameters {} but it was {}".format(
                request.httpMethod, request.url, request.params, params)
            assert jsonMatches, "expected {} {} to have json {} but it was {}".format(
                request.httpMethod, request.url, request.json, json)
            assert dataMatches, "expected {} {} to have data {} but it was {}".format(
                request.httpMethod, request.url, request.data, data)
        elif request.mode == ExpectedRequest.UNTIL:
            if matches:
                self.expectations.pop(0)
                return request

    def finalValidation(self):
        error_message = ""
        if self.expectations:
            error_message += "expected to receive {} more messages, but did not".format(
                len(self.expectations))

            for e in self.expectations:
                msg = "\n  {} {}".format(e.httpMethod, e.url)
                error_message += msg

        if self.inFlight:
            error_message += "expected to have all requests explicitely processed, but {} are still in flight".format(
                len(self.inFlight))

            for e in self.inFlight:
                e = self.inFlight[e]
                msg = "\n  {} {}".format(e.httpMethod, e.url)
                error_message += msg

        self.expectations = []
        self.record_id = 0
        self.record = []
        self.inFlight = {}

        if error_message:
            assert False, error_message

    def addInFlight(self, method, url, params, json, data):
        self.record_id += 1
        request = self.validateIsExpected(method, url, params, json, data)

        self.record.extend([self.record_id, method, url])
        in_flight = GCEAsyncResult(self.record_id)
        self.inFlight[self.record_id] = request
        return in_flight

    def interceptRequest(self, method, url, params={}, json={}, data=None, **kwargs):
        return self.addInFlight(method.upper(), url, params=params, json=json, data=data)

    def validateRes(self, inFlight, url=None):
        # Check that the entry exists and delete it
        request = self.inFlight[inFlight.record_id]
        del self.inFlight[inFlight.record_id]

        if request.resultCode not in (200, 201, 202):
            raise gceclientservice.GCEError(request.result)
        return request.result
