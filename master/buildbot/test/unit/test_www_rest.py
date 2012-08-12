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

from buildbot.www import rest
from buildbot.test.util import www
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
