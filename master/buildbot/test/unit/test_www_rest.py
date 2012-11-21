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

from cStringIO import StringIO
from buildbot.www import rest
from buildbot.test.util import www
from buildbot.util import json
from buildbot.data import exceptions
from twisted.trial import unittest
from twisted.internet import defer

class RestRootResource(www.WwwTestMixin, unittest.TestCase):

    maxVersion = 2

    def test_render(self):
        master = self.make_master(url='h:/a/b/')
        rsrc = rest.RestRootResource(master)

        d = self.render_resource(rsrc, [''])
        @d.addCallback
        def check(rv):
            self.assertIn('api_versions', rv)
        return d

    def test_versions(self):
        master = self.make_master(url='h:/a/b/')
        rsrc = rest.RestRootResource(master)
        self.assertEqual(sorted(rsrc.listNames()),
                sorted([ 'latest' ] +
                    [ 'v%d' % v for v in range(1, self.maxVersion+1) ]))

    def test_versions_limited(self):
        master = self.make_master(url='h:/a/b/')
        master.config.www['rest_minimum_version'] = 3 # start at v3
        rsrc = rest.RestRootResource(master)
        self.assertEqual(sorted(rsrc.listNames()),
                sorted([ 'latest' ] +
                    [ 'v%d' % v for v in range(3, self.maxVersion+1) ]))

class V2RootResource(www.WwwTestMixin, unittest.TestCase):

    def setUp(self):
        self.master = self.make_master(url='h:/')
        # patch out get to return its arguments
        def get(options, path):
            if path == ('not', 'found'):
                return defer.fail(exceptions.InvalidPathError())
            else:
                rv = options.copy()
                rv['path'] = path
                return defer.succeed(rv)
        self.master.data.get = get
        def control(action, args, path):
            if path == ('not', 'found'):
                return defer.fail(exceptions.InvalidPathError())
            elif action == "notfound":
                return defer.fail(exceptions.InvalidActionException())
            else:
                rv = dict(orig_args=args.copy(),
                          path = path)
                return defer.succeed(rv)
        self.master.data.control = control
        self.rsrc = rest.V2RootResource(self.master)

    def test_not_found(self):
        d = self.render_resource(self.rsrc, ['not', 'found'])
        @d.addCallback
        def check(_):
            self.assertRequest(
                contentJson=dict(error='invalid path'),
                contentType='text/plain',
                responseCode=404)
        return d

    def test_api_req(self):
        d = self.render_resource(self.rsrc, ['some', 'path'])
        @d.addCallback
        def check(_):
            self.assertRequest(
                contentJson=dict(path=['some', 'path']),
                contentType='application/json',
                responseCode=200,
                contentDisposition="attachment; filename=\"/req.path.json\"" )
        return d

    def test_api_req_as_text(self):
        d = self.render_resource(self.rsrc, ['some', 'path'],
                                        args={'as_text': ['1']})
        @d.addCallback
        def check(_):
            self.assertRequest(
                # note whitespace here:
                content='{\n  "path": [\n    "some", \n    "path"\n  ]\n}',
                contentType='text/plain',
                responseCode=200,
                contentDisposition=None)
        return d

    def test_api_req_as_text_compact(self):
        d = self.render_resource(self.rsrc, ['some', 'path'],
                args={'as_text': ['1'], 'compact': ['1']})
        @d.addCallback
        def check(_):
            self.assertRequest(
                # note *no* whitespace here:
                content='{"path":["some","path"]}',
                contentType='text/plain',
                responseCode=200,
                contentDisposition=None)
        return d

    def test_api_req_filter(self):
        d = self.render_resource(self.rsrc, ['some', 'path'],
                args={'filter': ['1'], 'empty': [''], 'full': ['a']})
        @d.addCallback
        def check(_):
            self.assertRequest(
                contentJson={'full': 'a', 'path': ['some', 'path']},
                responseCode=200)
        return d

    def test_api_req_callback(self):
        d = self.render_resource(self.rsrc, ['cb'],
                args={'callback': ['mycb']})
        @d.addCallback
        def check(_):
            self.assertRequest(content='mycb({"path":["cb"]});',
                               responseCode=200)
        return d
    def test_control_not_found(self):
        d = self.render_control_resource(self.rsrc, ['not', 'found'],{"action":["test"]},
                                         jsonRpc=False)
        @d.addCallback
        def check(_):
            self.assertRequest(
                contentJson=dict(error='invalid path'),
                contentType='text/plain',
                responseCode=404)
        return d

    def test_control_no_action(self):
        d = self.render_control_resource(self.rsrc, ['not', 'found'], jsonRpc=False)
        @d.addCallback
        def check(_):
            self.assertRequest(
                contentJson=dict(error='need an action parameter for POST'),
                contentType='text/plain',
                responseCode=400)
        return d

    def test_control_urlencoded(self):
        d = self.render_control_resource(self.rsrc, ['path'],{"action":["test"],"param1":["foo"]}, jsonRpc=False)
        @d.addCallback
        def check(_):
            self.assertRequest(
                contentJson={'orig_args': {'param1': 'foo'}, 'path': ['path']},
                contentType='application/json',
                responseCode=200)
        return d

    def test_controljs_not_found(self):
        d = self.render_control_resource(self.rsrc, ['not', 'found'],action="test",
                                         jsonRpc=True)
        @d.addCallback
        def check(_):
            self.assertRequest(
                errorJsonRPC={'code': -32603, 'message': 'invalid path'},
                contentType='application/json',
                responseCode=404)
        return d

    def test_controljs_badaction(self):
        d = self.render_control_resource(self.rsrc, ['path'],{"param1":["foo"]},
                                         jsonRpc=True)
        @d.addCallback
        def check(_):
            self.assertRequest(
                errorJsonRPC={'code': -32601, 'message': 'invalid method'},
                contentType='application/json',
                responseCode=501)
        return d
    def dotest_controljs_malformedjson(self, _json, error, noIdCheck=False, httpcode=400):
        request = self.make_request(['path'])
        request.content = StringIO(json.dumps(_json))
        request.input_headers = {'content-type': 'application/json'}
        d = self.render_control_resource(self.rsrc,
                                         request = request,
                                         jsonRpc=not noIdCheck)
        @d.addCallback
        def check(_):
            self.assertRequest(
                errorJsonRPC=error,
                contentType='application/json',
                responseCode=httpcode)
        return d
    def test_controljs_malformedjson1(self):
        return self.dotest_controljs_malformedjson(
            [ "list_not_supported"],
            {'code': -32600, 'message': 'jsonrpc call batch is not supported'}
            ,noIdCheck=True)

    def test_controljs_malformedjson_no_dict(self):
        return self.dotest_controljs_malformedjson(
            "str_not_supported",
            {'code': -32600, 'message': 'json root object must be a dictionary: "str_not_supported"'}
            ,noIdCheck=True)
    def test_controljs_malformedjson_nojsonrpc(self):
        return self.dotest_controljs_malformedjson(
            { "method": "action", "params": {"arg":"args"}, "id": "_id"},
            {'code': -32600, 'message': "need 'jsonrpc' to be present and be a <type 'str'>"}
            ,noIdCheck=True)
    def test_controljs_malformedjson_no_method(self):
        return self.dotest_controljs_malformedjson(
            { "jsonrpc": "2.0", "params": {"arg":"args"}, "id": "_id"},
            {'code': -32600, 'message': "need 'method' to be present and be a <type 'str'>"}
            ,noIdCheck=True)
    def test_controljs_malformedjson_no_param(self):
        return self.dotest_controljs_malformedjson(
            { "jsonrpc": "2.0", "method": "action",  "id": "_id"},
            {'code': -32600, 'message': "need 'params' to be present and be a <type 'dict'>"}
            ,noIdCheck=True)
    def test_controljs_malformedjson_bad_param(self):
        return self.dotest_controljs_malformedjson(
            { "jsonrpc": "2.0", "method":"action", "params": ["args"], "id": "_id"},
            {'code': -32600, 'message': "need 'params' to be present and be a <type 'dict'>"}
            ,noIdCheck=True)
    def test_controljs_malformedjson_no_id(self):
        return self.dotest_controljs_malformedjson(
            { "jsonrpc": "2.0", "method": "action",  "params": {"arg":"args"} },
            {'code': -32600, 'message': "need 'id' to be present and be a <type 'str'>"}
            ,noIdCheck=True)
