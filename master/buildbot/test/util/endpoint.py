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

import mock
from twisted.internet import defer
from buildbot.test.fake import fakemaster
from buildbot.test.util import interfaces

class EndpointMixin(interfaces.InterfaceTests):
    # test mixin for testing Endpoint subclasses

    # class being tested
    endpointClass = None

    # if necessary, the corresponding resource type - this wil
    # be instantiated at self.data.rtypes[rtype.type] and self.rtype
    resourceTypeClass = None

    def setUpEndpoint(self):
        self.master = fakemaster.make_master(wantMq=True, wantDb=True,
                wantData=True, testcase=self)
        self.db = self.master.db
        self.mq = self.master.mq
        self.data = self.master.data
        self.ep = self.endpointClass(self.master)

        if self.resourceTypeClass:
            rtype = self.rtype = self.resourceTypeClass(self.master)
            self.data.rtypes = { rtype.type : rtype }

        # this usually fails when a single-element pathPattern does not have a
        # trailing comma
        patterns = [ self.ep.pathPattern ] + self.ep.pathPatterns
        for pp in patterns:
            if pp is not None:
                self.assertIsInstance(pp, tuple)

        self.pathArgs = [
            set([ arg.split(':', 1)[1] for arg in pp if ':' in arg ])
            for pp in patterns if pp is not None ]

    def tearDownEndpoint(self):
        pass

    # call methods, with extra checks

    def callGet(self, options, kwargs):
        self.assertIn(set(kwargs), self.pathArgs)
        d = self.ep.get(options, kwargs)
        self.assertIsInstance(d, defer.Deferred)
        return d

    def callStartConsuming(self, options, kwargs, expected_filter=None):
        self.assertIn(set(kwargs), self.pathArgs)
        cb = mock.Mock()
        qref = self.ep.startConsuming(cb, options, kwargs)
        self.assertTrue(hasattr(qref, 'stopConsuming'))
        self.assertIdentical(self.mq.qrefs[0], qref)
        self.assertIdentical(qref.callback, cb)
        self.assertEqual(qref.filter, expected_filter)


    # interface tests

    def test_get_spec(self):
        @self.assertArgSpecMatches(self.ep.get)
        def get(self, options, kwargs):
            pass

    def test_startConsuming_spec(self):
        @self.assertArgSpecMatches(self.ep.startConsuming)
        def startConsuming(self, callback, options, kwargs):
            pass

    def test_control_spec(self):
        @self.assertArgSpecMatches(self.ep.control)
        def control(self, action, args, kwargs):
            pass
