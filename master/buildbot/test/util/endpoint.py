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

from twisted.internet import defer

from buildbot.data import base
from buildbot.data import resultspec
from buildbot.test.fake import fakemaster
from buildbot.test.util import interfaces
from buildbot.test.util import validation
from buildbot.util import pathmatch


class EndpointMixin(interfaces.InterfaceTests):
    # test mixin for testing Endpoint subclasses

    # class being tested
    endpointClass = None

    # the corresponding resource type - this will be instantiated at
    # self.data.rtypes[rtype.type] and self.rtype
    resourceTypeClass = None

    def setUpEndpoint(self):
        self.master = fakemaster.make_master(wantMq=True, wantDb=True,
                                             wantData=True, testcase=self)
        self.db = self.master.db
        self.mq = self.master.mq
        self.data = self.master.data
        self.matcher = pathmatch.Matcher()

        rtype = self.rtype = self.resourceTypeClass(self.master)
        setattr(self.data.rtypes, rtype.name, rtype)

        self.ep = self.endpointClass(rtype, self.master)

        # this usually fails when a single-element pathPattern does not have a
        # trailing comma
        pathPatterns = self.ep.pathPatterns.split()
        for pp in pathPatterns:
            if pp == '/':
                continue
            if not pp.startswith('/') or pp.endswith('/'):
                raise AssertionError("invalid pattern %r" % (pp,))
        pathPatterns = [tuple(pp.split('/')[1:])
                        for pp in pathPatterns]
        for pp in pathPatterns:
            self.matcher[pp] = self.ep

        self.pathArgs = [
            set([arg.split(':', 1)[1] for arg in pp if ':' in arg])
            for pp in pathPatterns if pp is not None]

    def tearDownEndpoint(self):
        pass

    def validateData(self, object):
        validation.verifyData(self, self.rtype.entityType, {}, object)

    # call methods, with extra checks

    def callGet(self, path, resultSpec=None):
        self.assertIsInstance(path, tuple)
        if resultSpec is None:
            resultSpec = resultspec.ResultSpec()
        endpoint, kwargs = self.matcher[path]
        self.assertIdentical(endpoint, self.ep)
        d = endpoint.get(resultSpec, kwargs)
        self.assertIsInstance(d, defer.Deferred)

        @d.addCallback
        def checkNumber(rv):
            if self.ep.isCollection:
                self.assertIsInstance(rv, (list, base.ListResult))
            else:
                self.assertIsInstance(rv, (dict, type(None)))
            return rv
        return d

    def callControl(self, action, args, path):
        self.assertIsInstance(path, tuple)
        endpoint, kwargs = self.matcher[path]
        self.assertIdentical(endpoint, self.ep)
        d = self.ep.control(action, args, kwargs)
        self.assertIsInstance(d, defer.Deferred)
        return d

    # interface tests

    def test_get_spec(self):
        @self.assertArgSpecMatches(self.ep.get)
        def get(self, resultSpec, kwargs):
            pass

    def test_control_spec(self):
        @self.assertArgSpecMatches(self.ep.control)
        def control(self, action, args, kwargs):
            pass

    def test_rootLinkName(self):
        rootLinkName = self.ep.rootLinkName
        if not rootLinkName:
            return
        try:
            self.assertEqual(self.matcher[(rootLinkName,)][0], self.ep)
        except KeyError:
            self.fail('No match for rootlink: ' + rootLinkName)
