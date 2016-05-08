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
import re

import mock
from future.utils import iteritems
from future.utils import itervalues
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.test.fake import endpoint
from buildbot.test.util import www
from buildbot.util import json
from buildbot.www import authz
from buildbot.www import rest
from buildbot.www.rest import JSONRPC_CODES
from buildbot.www.rest import BadRequest


class RestRootResource(www.WwwTestMixin, unittest.TestCase):

    maxVersion = 2

    def test_render(self):
        master = self.make_master(url='h:/a/b/')
        rsrc = rest.RestRootResource(master)

        d = self.render_resource(rsrc, '/')

        @d.addCallback
        def check(rv):
            self.assertIn('api_versions', rv)
        return d

    def test_versions(self):
        master = self.make_master(url='h:/a/b/')
        rsrc = rest.RestRootResource(master)
        self.assertEqual(sorted(rsrc.listNames()),
                         sorted(['latest'] +
                                ['v%d' % v for v in range(2, self.maxVersion + 1)]))

    def test_versions_limited(self):
        master = self.make_master(url='h:/a/b/')
        master.config.www['rest_minimum_version'] = 2
        rsrc = rest.RestRootResource(master)
        self.assertEqual(sorted(rsrc.listNames()),
                         sorted(['latest'] +
                                ['v%d' % v for v in range(2, self.maxVersion + 1)]))


class V2RootResource(www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.master = self.make_master(url='http://server/path/')
        self.master.data._scanModule(endpoint)
        self.rsrc = rest.V2RootResource(self.master)
        self.rsrc.reconfigResource(self.master.config)

    def assertSimpleError(self, message, responseCode):
        self.assertRequest(content=json.dumps({'error': message}),
                           responseCode=responseCode)

    @defer.inlineCallbacks
    def test_failure(self):
        self.rsrc.renderRest = mock.Mock(
            return_value=defer.fail(RuntimeError('oh noes')))
        yield self.render_resource(self.rsrc, '/')
        self.assertSimpleError('internal error - see logs', 500)
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    @defer.inlineCallbacks
    def test_invalid_http_method(self):
        yield self.render_resource(self.rsrc, '/', method='PATCH')
        self.assertSimpleError('invalid HTTP method', 400)

    def test_default_origin(self):
        self.master.config.buildbotURL = 'http://server/path/'
        self.rsrc.reconfigResource(self.master.config)
        self.assertEqual(
            [r.pattern for r in self.rsrc.origins], [r'http\:\/\/server\Z(?ms)'])

        self.master.config.buildbotURL = 'http://server/'
        self.rsrc.reconfigResource(self.master.config)
        self.assertEqual(
            [r.pattern for r in self.rsrc.origins], [r'http\:\/\/server\Z(?ms)'])

        self.master.config.buildbotURL = 'http://server:8080/'
        self.rsrc.reconfigResource(self.master.config)
        self.assertEqual(
            [r.pattern for r in self.rsrc.origins], [r'http\:\/\/server\:8080\Z(?ms)'])

        self.master.config.buildbotURL = 'https://server:8080/'
        self.rsrc.reconfigResource(self.master.config)
        self.assertEqual(
            [r.pattern for r in self.rsrc.origins], [r'https\:\/\/server\:8080\Z(?ms)'])


class V2RootResource_CORS(www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.master = self.make_master(url='h:/')
        self.master.data._scanModule(endpoint)
        self.rsrc = rest.V2RootResource(self.master)
        self.master.config.www['allowed_origins'] = ['h://good']
        self.rsrc.reconfigResource(self.master.config)

        def renderRest(request):
            request.write('ok')
            return defer.succeed(None)
        self.rsrc.renderRest = renderRest

    def assertOk(self, expectHeaders=True, content='ok', origin='h://good'):
        hdrs = {
            'access-control-allow-origin': [origin],
            'access-control-allow-headers': ['Content-Type'],
            'access-control-max-age': ['3600'],
        } if expectHeaders else {}
        self.assertRequest(content=content, responseCode=200, headers=hdrs)

    def assertNotOk(self, message):
        self.assertRequest(content=json.dumps({'error': message}),
                           responseCode=400)

    @defer.inlineCallbacks
    def test_cors_no_origin(self):
        # if the browser doesn't send Origin, there's nothing we can do to
        # protect the user
        yield self.render_resource(self.rsrc, '/')
        self.assertOk(expectHeaders=False)

    @defer.inlineCallbacks
    def test_cors_origin_match(self):
        yield self.render_resource(self.rsrc, '/', origin='h://good')
        self.assertOk()

    @defer.inlineCallbacks
    def test_cors_origin_match_star(self):
        self.master.config.www['allowed_origins'] = ['*']
        self.rsrc.reconfigResource(self.master.config)
        yield self.render_resource(self.rsrc, '/', origin='h://good')
        self.assertOk()

    @defer.inlineCallbacks
    def test_cors_origin_patterns(self):
        self.master.config.www['allowed_origins'] = ['h://*.good',
                                                     'hs://*.secure']
        self.rsrc.reconfigResource(self.master.config)
        yield self.render_resource(self.rsrc, '/', origin='h://foo.good')
        self.assertOk(origin='h://foo.good')
        yield self.render_resource(self.rsrc, '/', origin='hs://x.secure')
        self.assertOk(origin='hs://x.secure')
        yield self.render_resource(self.rsrc, '/', origin='h://x.secure')
        self.assertNotOk('invalid origin')

    @defer.inlineCallbacks
    def test_cors_origin_mismatch(self):
        yield self.render_resource(self.rsrc, '/', origin='h://bad')
        self.assertNotOk('invalid origin')

    @defer.inlineCallbacks
    def test_cors_origin_preflight_match_GET(self):
        yield self.render_resource(self.rsrc, '/',
                                   method='OPTIONS', origin='h://good',
                                   access_control_request_method='GET')
        self.assertOk(content='')

    @defer.inlineCallbacks
    def test_cors_origin_preflight_match_POST(self):
        yield self.render_resource(self.rsrc, '/',
                                   method='OPTIONS', origin='h://good',
                                   access_control_request_method='POST')
        self.assertOk(content='')

    @defer.inlineCallbacks
    def test_cors_origin_preflight_bad_method(self):
        yield self.render_resource(self.rsrc, '/',
                                   method='OPTIONS', origin='h://good',
                                   access_control_request_method='PATCH')
        self.assertNotOk(message='invalid method')

    @defer.inlineCallbacks
    def test_cors_origin_preflight_bad_origin(self):
        yield self.render_resource(self.rsrc, '/',
                                   method='OPTIONS', origin='h://bad',
                                   access_control_request_method='GET')
        self.assertNotOk(message='invalid origin')


class V2RootResource_REST(www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.master = self.make_master(url='h:/')
        self.master.config.www['debug'] = True
        self.master.data._scanModule(endpoint)
        self.rsrc = rest.V2RootResource(self.master)
        self.rsrc.reconfigResource(self.master.config)

        endpoint.TestEndpoint.rtype = mock.MagicMock()
        endpoint.TestsEndpoint.rtype = mock.MagicMock()
        endpoint.Test.isCollection = True
        endpoint.Test.rtype = endpoint.Test

    def assertRestCollection(self, typeName, items,
                             total=None, contentType=None, orderSignificant=False):
        self.failIf(isinstance(self.request.written, unicode))
        got = {}
        got['content'] = json.loads(self.request.written)
        got['contentType'] = self.request.headers['content-type']
        got['responseCode'] = self.request.responseCode

        meta = {}
        if total is not None:
            meta['total'] = total

        exp = {}
        exp['content'] = {typeName: items, 'meta': meta}
        exp['contentType'] = [contentType or 'text/plain; charset=utf-8']
        exp['responseCode'] = 200

        # if order is not significant, sort so the comparison works
        if not orderSignificant:
            if 'content' in got and typeName in got['content']:
                got['content'][typeName].sort()
            exp['content'][typeName].sort()
        if 'meta' in got['content'] and 'links' in got['content']['meta']:
            got['content']['meta']['links'].sort(
                key=lambda l: (l['rel'], l['href']))

        self.assertEqual(got, exp)

    def assertRestDetails(self, typeName, item,
                          contentType=None):
        got = {}
        got['content'] = json.loads(self.request.written)
        got['contentType'] = self.request.headers['content-type']
        got['responseCode'] = self.request.responseCode

        exp = {}
        exp['content'] = {
            typeName: [item],
            'meta': {},
        }
        exp['contentType'] = [contentType or 'text/plain; charset=utf-8']
        exp['responseCode'] = 200

        self.assertEqual(got, exp)

    def assertRestError(self, responseCode, message):
        got = {}
        got['content'] = json.loads(self.request.written)
        got['responseCode'] = self.request.responseCode

        exp = {}
        exp['content'] = {'error': message}
        exp['responseCode'] = responseCode

        self.assertEqual(got, exp)

    @defer.inlineCallbacks
    def test_not_found(self):
        yield self.render_resource(self.rsrc, '/not/found')
        self.assertRequest(
            contentJson=dict(error='Invalid path: not/found'),
            contentType='text/plain; charset=utf-8',
            responseCode=404)

    @defer.inlineCallbacks
    def test_invalid_query(self):
        yield self.render_resource(self.rsrc, '/test?huh=1')
        self.assertRequest(
            contentJson=dict(error="unrecognized query parameter 'huh'"),
            contentType='text/plain; charset=utf-8',
            responseCode=400)

    @defer.inlineCallbacks
    def test_raw(self):
        yield self.render_resource(self.rsrc, '/rawtest')
        self.assertRequest(
            content="value",
            contentType='text/test; charset=utf-8',
            responseCode=200,
            headers={"content-disposition": ['attachment; filename=test.txt']})

    @defer.inlineCallbacks
    def test_api_head(self):
        get = yield self.render_resource(self.rsrc, '/test', method='GET')
        head = yield self.render_resource(self.rsrc, '/test', method='HEAD')
        self.assertEqual(head, '')
        self.assertEqual(int(self.request.headers['content-length'][0]),
                         len(get))

    @defer.inlineCallbacks
    def test_api_collection(self):
        yield self.render_resource(self.rsrc, '/test')
        self.assertRestCollection(typeName='tests',
                                  items=list(itervalues(endpoint.testData)),
                                  total=8)

    @defer.inlineCallbacks
    def do_test_api_collection_pagination(self, query, ids, links):
        yield self.render_resource(self.rsrc, '/test' + query)
        self.assertRestCollection(typeName='tests',
                                  items=[v for k, v in iteritems(endpoint.testData)
                                         if k in ids],
                                  total=8)

    def test_api_collection_limit(self):
        return self.do_test_api_collection_pagination('?limit=2',
                                                      [13, 14], {
                                                          'self': '%(self)s?limit=2',
                                                          'next': '%(self)s?offset=2&limit=2',
                                                      })

    def test_api_collection_offset(self):
        return self.do_test_api_collection_pagination('?offset=2',
                                                      [15, 16, 17, 18, 19, 20], {
                                                          'self': '%(self)s?offset=2',
                                                          'first': '%(self)s',
                                                      })

    def test_api_collection_offset_limit(self):
        return self.do_test_api_collection_pagination('?offset=5&limit=2',
                                                      [18, 19], {
                                                          'first': '%(self)s?limit=2',
                                                          'prev': '%(self)s?offset=3&limit=2',
                                                          'next': '%(self)s?offset=7&limit=2',
                                                          'self': '%(self)s?offset=5&limit=2',
                                                      })

    def test_api_collection_limit_at_end(self):
        return self.do_test_api_collection_pagination('?offset=5&limit=3',
                                                      [18, 19, 20], {
                                                          'first': '%(self)s?limit=3',
                                                          'prev': '%(self)s?offset=2&limit=3',
                                                          'self': '%(self)s?offset=5&limit=3',
                                                      })

    def test_api_collection_limit_past_end(self):
        return self.do_test_api_collection_pagination('?offset=5&limit=20',
                                                      [18, 19, 20], {
                                                          'first': '%(self)s?limit=20',
                                                          'prev': '%(self)s?limit=5',
                                                          'self': '%(self)s?offset=5&limit=20',
                                                      })

    def test_api_collection_offset_past_end(self):
        return self.do_test_api_collection_pagination('?offset=50&limit=10',
                                                      [], {
                                                          'first': '%(self)s?limit=10',
                                                          'prev': '%(self)s?offset=40&limit=10',
                                                          'self': '%(self)s?offset=50&limit=10',
                                                      })

    @defer.inlineCallbacks
    def test_api_collection_invalid_limit(self):
        yield self.render_resource(self.rsrc, '/test?limit=foo!')
        self.assertRequest(
            contentJson=dict(error="invalid limit"),
            contentType='text/plain; charset=utf-8',
            responseCode=400)

    @defer.inlineCallbacks
    def test_api_collection_invalid_offset(self):
        yield self.render_resource(self.rsrc, '/test?offset=foo!')
        self.assertRequest(
            contentJson=dict(error="invalid offset"),
            contentType='text/plain; charset=utf-8',
            responseCode=400)

    @defer.inlineCallbacks
    def test_api_collection_invalid_simple_filter_value(self):
        yield self.render_resource(self.rsrc, '/test?success=sorta')
        self.assertRequest(
            contentJson=dict(error="invalid filter value for success"),
            contentType='text/plain; charset=utf-8',
            responseCode=400)

    @defer.inlineCallbacks
    def test_api_collection_invalid_filter_value(self):
        yield self.render_resource(self.rsrc, '/test?id__lt=fifteen')
        self.assertRequest(
            contentJson=dict(error="invalid filter value for id__lt"),
            contentType='text/plain; charset=utf-8',
            responseCode=400)

    @defer.inlineCallbacks
    def test_api_collection_fields(self):
        yield self.render_resource(self.rsrc, '/test?field=success&field=info')
        self.assertRestCollection(typeName='tests',
                                  items=[{'success': v['success'], 'info': v['info']}
                                         for v in itervalues(endpoint.testData)],
                                  total=8)

    @defer.inlineCallbacks
    def test_api_collection_invalid_field(self):
        yield self.render_resource(self.rsrc, '/test?field=success&field=WTF')
        self.assertRequest(
            contentJson=dict(error="no such field 'WTF'"),
            contentType='text/plain; charset=utf-8',
            responseCode=400)

    @defer.inlineCallbacks
    def test_api_collection_simple_filter(self):
        yield self.render_resource(self.rsrc, '/test?success=yes')
        self.assertRestCollection(typeName='tests',
                                  items=[v for v in itervalues(endpoint.testData)
                                         if v['success']],
                                  total=5)

    @defer.inlineCallbacks
    def test_api_collection_list_filter(self):
        yield self.render_resource(self.rsrc, '/test?tags__contains=a')
        self.assertRestCollection(typeName='tests',
                                  items=[v for v in itervalues(endpoint.testData)
                                         if 'a' in v['tags']],
                                  total=2)

    @defer.inlineCallbacks
    def test_api_collection_operator_filter(self):
        yield self.render_resource(self.rsrc, '/test?info__lt=skipped')
        self.assertRestCollection(typeName='tests',
                                  items=[v for v in itervalues(endpoint.testData)
                                         if v['info'] < 'skipped'],
                                  total=4)

    @defer.inlineCallbacks
    def test_api_collection_order(self):
        yield self.render_resource(self.rsrc, '/test?order=info')
        self.assertRestCollection(typeName='tests',
                                  items=sorted(list(itervalues(endpoint.testData)),
                                               key=lambda v: v['info']),
                                  total=8, orderSignificant=True)

    @defer.inlineCallbacks
    def test_api_collection_order_on_unselected(self):
        yield self.render_resource(self.rsrc, '/test?field=id&order=info')
        self.assertRestError(message="cannot order on un-selected fields",
                             responseCode=400)

    @defer.inlineCallbacks
    def test_api_collection_filter_on_unselected(self):
        yield self.render_resource(self.rsrc, '/test?field=id&info__gt=xx')
        self.assertRestError(message="cannot filter on un-selected fields",
                             responseCode=400)

    @defer.inlineCallbacks
    def test_api_collection_filter_pagination(self):
        yield self.render_resource(self.rsrc, '/test?success=false&limit=2')
        # note that the limit/offset and total are *after* the filter
        self.assertRestCollection(typeName='tests',
                                  items=sorted([v for v in itervalues(endpoint.testData)
                                                if not v['success']], key=lambda v: v['id'])[:2],
                                  total=3)

    @defer.inlineCallbacks
    def test_api_details(self):
        yield self.render_resource(self.rsrc, '/test/13')
        self.assertRestDetails(typeName='tests',
                               item=endpoint.testData[13])

    @defer.inlineCallbacks
    def test_api_details_none(self):
        yield self.render_resource(self.rsrc, '/test/0')
        self.assertRequest(
            contentJson={u'error': u"not found while getting from endpoint for /test/n:testid with arguments"
                                   " ResultSpec(**{'limit': None, 'filters': [], 'offset': None, "
                                   "'fields': None, 'order': None, 'properties': []}) and {'testid': 0}"},
            contentType='text/plain; charset=utf-8',
            responseCode=404)

    @defer.inlineCallbacks
    def test_api_details_filter_fails(self):
        yield self.render_resource(self.rsrc, '/test/13?success=false')
        self.assertRequest(
            contentJson=dict(error="this is not a collection"),
            contentType='text/plain; charset=utf-8',
            responseCode=400)

    @defer.inlineCallbacks
    def test_api_details_fields(self):
        yield self.render_resource(self.rsrc, '/test/13?field=info')
        self.assertRestDetails(typeName='tests',
                               item={'info': endpoint.testData[13]['info']})

    @defer.inlineCallbacks
    def test_api_with_accept(self):
        # when 'application/json' is accepted, the result has that type
        yield self.render_resource(self.rsrc, '/test/13',
                                   accept='application/json')
        self.assertRestDetails(typeName='tests',
                               item=endpoint.testData[13],
                               contentType='application/json; charset=utf-8')

    @defer.inlineCallbacks
    def test_api_fails(self):
        yield self.render_resource(self.rsrc, '/test/fail')
        self.assertRestError(message="RuntimeError('oh noes',)",
                             responseCode=500)
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    def test_decode_result_spec_raise_bad_request_on_bad_property_value(self):
        expected_props = [None, 'test2']
        self.make_request('/test')
        self.request.args = {'property': expected_props}
        self.assertRaises(BadRequest, lambda: self.rsrc.decodeResultSpec(
            self.request, endpoint.TestsEndpoint))

    def test_decode_result_spec_limit(self):
        expected_limit = 5
        self.make_request('/test')
        self.request.args = {'limit': str(expected_limit)}
        spec = self.rsrc.decodeResultSpec(self.request, endpoint.TestsEndpoint)
        self.assertEqual(spec.limit, expected_limit)

    def test_decode_result_spec_order(self):
        expected_order = 'info',
        self.make_request('/test')
        self.request.args = {'order': expected_order}
        spec = self.rsrc.decodeResultSpec(self.request, endpoint.Test)
        self.assertEqual(spec.order, expected_order)

    def test_decode_result_spec_offset(self):
        expected_offset = 5
        self.make_request('/test')
        self.request.args = {'offset': str(expected_offset)}
        spec = self.rsrc.decodeResultSpec(self.request, endpoint.TestsEndpoint)
        self.assertEqual(spec.offset, expected_offset)

    def test_decode_result_spec_properties(self):
        expected_props = ['test1', 'test2']
        self.make_request('/test')
        self.request.args = {'property': expected_props}
        spec = self.rsrc.decodeResultSpec(self.request, endpoint.TestsEndpoint)
        self.assertEqual(spec.properties[0].values, expected_props)

    def test_decode_result_spec_not_a_collection_limit(self):
        def expectRaiseBadRequest():
            limit = 5
            self.make_request('/test')
            self.request.args = {'limit': limit}
            self.rsrc.decodeResultSpec(self.request, endpoint.TestEndpoint)
        self.assertRaises(rest.BadRequest, expectRaiseBadRequest)

    def test_decode_result_spec_not_a_collection_order(self):
        def expectRaiseBadRequest():
            order = 'info',
            self.make_request('/test')
            self.request.args = {'order': order}
            self.rsrc.decodeResultSpec(self.request, endpoint.TestEndpoint)
        self.assertRaises(rest.BadRequest, expectRaiseBadRequest)

    def test_decode_result_spec_not_a_collection_offset(self):
        def expectRaiseBadRequest():
            offset = 0
            self.make_request('/test')
            self.request.args = {'offset': offset}
            self.rsrc.decodeResultSpec(self.request, endpoint.TestEndpoint)
        self.assertRaises(rest.BadRequest, expectRaiseBadRequest)

    def test_decode_result_spec_not_a_collection_properties(self):
        expected_props = ['test1', 'test2']
        self.make_request('/test')
        self.request.args = {'property': expected_props}
        spec = self.rsrc.decodeResultSpec(self.request, endpoint.TestEndpoint)
        self.assertEqual(spec.properties[0].values, expected_props)


class V2RootResource_JSONRPC2(www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.master = self.make_master(url='h:/')

        def allow(*args, **kw):
            return
        self.master.www.assertUserAllowed = allow

        self.master.data._scanModule(endpoint)
        self.rsrc = rest.V2RootResource(self.master)
        self.rsrc.reconfigResource(self.master.config)

    def assertJsonRpcError(self, message, responseCode=400, jsonrpccode=None):
        got = {}
        got['contentType'] = self.request.headers['content-type']
        got['responseCode'] = self.request.responseCode
        content = json.loads(self.request.written)
        if ('error' not in content
                or sorted(content['error'].keys()) != ['code', 'message']):
            self.fail("response does not have proper error form: %r"
                      % (content,))
        got['error'] = content['error']

        exp = {}
        exp['contentType'] = ['application/json']
        exp['responseCode'] = responseCode
        exp['error'] = {'code': jsonrpccode, 'message': message}

        # process a regular expression for message, if given
        if not isinstance(message, basestring):
            if message.match(got['error']['message']):
                exp['error']['message'] = got['error']['message']
            else:
                exp['error']['message'] = "MATCHING: %s" % (message.pattern,)

        self.assertEqual(got, exp)

    @defer.inlineCallbacks
    def test_invalid_path(self):
        yield self.render_control_resource(self.rsrc, '/not/found')
        self.assertJsonRpcError(
            message='Invalid path: not/found',
            jsonrpccode=JSONRPC_CODES['invalid_request'],
            responseCode=404)

    @defer.inlineCallbacks
    def test_invalid_action(self):
        yield self.render_control_resource(self.rsrc, '/test', action='nosuch')
        self.assertJsonRpcError(
            message='invalid control action',
            jsonrpccode=JSONRPC_CODES['method_not_found'],
            responseCode=501)

    @defer.inlineCallbacks
    def test_invalid_json(self):
        yield self.render_control_resource(self.rsrc, '/test',
                                           requestJson="{abc")
        self.assertJsonRpcError(
            message=re.compile('^JSON parse error'),
            jsonrpccode=JSONRPC_CODES['parse_error'])

    @defer.inlineCallbacks
    def test_invalid_content_type(self):
        yield self.render_control_resource(self.rsrc, '/test',
                                           requestJson='{"jsonrpc": "2.0", "method": "foo",'
                                           '"id":"abcdef", "params": {}}',
                                           content_type='application/x-www-form-urlencoded')
        self.assertJsonRpcError(
            message=re.compile('Invalid content-type'),
            jsonrpccode=JSONRPC_CODES['invalid_request'])

    @defer.inlineCallbacks
    def test_list_request(self):
        yield self.render_control_resource(self.rsrc, '/test',
                                           requestJson="[1,2]")
        self.assertJsonRpcError(
            message="JSONRPC batch requests are not supported",
            jsonrpccode=JSONRPC_CODES['invalid_request'])

    @defer.inlineCallbacks
    def test_bad_req_type(self):
        yield self.render_control_resource(self.rsrc, '/test',
                                           requestJson='"a string?!"')
        self.assertJsonRpcError(
            message="JSONRPC root object must be an object",
            jsonrpccode=JSONRPC_CODES['invalid_request'])

    @defer.inlineCallbacks
    def do_test_invalid_req(self, requestJson, message):
        yield self.render_control_resource(self.rsrc, '/test',
                                           requestJson=requestJson)
        self.assertJsonRpcError(
            message=message,
            jsonrpccode=JSONRPC_CODES['invalid_request'])

    def test_bad_req_jsonrpc_missing(self):
        return self.do_test_invalid_req(
            '{"method": "foo", "id":"abcdef", "params": {}}',
            "missing key 'jsonrpc'")

    def test_bad_req_jsonrpc_type(self):
        return self.do_test_invalid_req(
            '{"jsonrpc": 13, "method": "foo", "id":"abcdef", "params": {}}',
            "'jsonrpc' must be a string")

    def test_bad_req_jsonrpc_value(self):
        return self.do_test_invalid_req(
            '{"jsonrpc": "3.0", "method": "foo", "id":"abcdef", "params": {}}',
            "only JSONRPC 2.0 is supported")

    def test_bad_req_method_missing(self):
        return self.do_test_invalid_req(
            '{"jsonrpc": "2.0", "id":"abcdef", "params": {}}',
            "missing key 'method'")

    def test_bad_req_method_type(self):
        return self.do_test_invalid_req(
            '{"jsonrpc": "2.0", "method": 999, "id":"abcdef", "params": {}}',
            "'method' must be a string")

    def test_bad_req_id_missing(self):
        return self.do_test_invalid_req(
            '{"jsonrpc": "2.0", "method": "foo", "params": {}}',
            "missing key 'id'")

    def test_bad_req_id_type(self):
        return self.do_test_invalid_req(
            '{"jsonrpc": "2.0", "method": "foo", "id": {}, "params": {}}',
            "'id' must be a string, number, or null")

    def test_bad_req_params_missing(self):
        return self.do_test_invalid_req(
            '{"jsonrpc": "2.0", "method": "foo", "id": "abc"}',
            "missing key 'params'")

    def test_bad_req_params_type(self):
        return self.do_test_invalid_req(
            '{"jsonrpc": "2.0", "method": "foo", "id": "abc", "params": 999}',
            "'params' must be an object")

    @defer.inlineCallbacks
    def test_valid(self):
        yield self.render_control_resource(self.rsrc, '/test/13',
                                           action="testy", params={'foo': 3, 'bar': 5})
        self.assertRequest(
            contentJson={
                'id': self.UUID,
                'jsonrpc': '2.0',
                'result': {
                    'action': 'testy',
                    'args': {'foo': 3, 'bar': 5,
                             'owner': 'anonymous'},
                    'kwargs': {'testid': 13},
                },
            },
            contentType='application/json',
            responseCode=200)

    @defer.inlineCallbacks
    def test_valid_int_id(self):
        yield self.render_control_resource(self.rsrc, '/test/13',
                                           action="testy", params={'foo': 3, 'bar': 5}, id=1823)
        self.assertRequest(
            contentJson={
                'id': 1823,
                'jsonrpc': '2.0',
                'result': {
                    'action': 'testy',
                    'args': {'foo': 3, 'bar': 5,
                             'owner': 'anonymous',
                             },
                    'kwargs': {'testid': 13},
                },
            },
            contentType='application/json',
            responseCode=200)

    @defer.inlineCallbacks
    def test_valid_fails(self):
        yield self.render_control_resource(self.rsrc, '/test/13',
                                           action="fail")
        self.assertJsonRpcError(
            message=re.compile('^RuntimeError'),
            jsonrpccode=JSONRPC_CODES['internal_error'],
            responseCode=500)
        # the error gets logged, too:
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    @defer.inlineCallbacks
    def test_authz_forbidden(self):

        @defer.inlineCallbacks
        def deny(request, ep, action, options):
            if "13" in ep:
                raise authz.Forbidden("no no")
            defer.returnValue(None)
        self.master.www.assertUserAllowed = deny
        yield self.render_control_resource(self.rsrc, '/test/13',
                                           action="fail")
        self.assertJsonRpcError(
            message=re.compile('no no'),
            jsonrpccode=JSONRPC_CODES['invalid_request'],
            responseCode=403)


class ContentTypeParser(unittest.TestCase):

    def test_simple(self):
        self.assertEqual(
            rest.ContentTypeParser("application/json").gettype(), "application/json")

    def test_complex(self):
        self.assertEqual(rest.ContentTypeParser("application/json; Charset=UTF-8").gettype(),
                         "application/json")

    def test_text(self):
        self.assertEqual(
            rest.ContentTypeParser("text/plain; Charset=UTF-8").gettype(), "text/plain")
