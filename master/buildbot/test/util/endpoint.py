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

from buildbot.test.fake import fakemaster, fakedb
from buildbot.test.util import interfaces

class EndpointMixin(interfaces.InterfaceTests):
    # test mixin for testing Endpoint subclasses

    endpointClass = None

    def setUpEndpoint(self, needDB=True):
        self.master = fakemaster.make_master()
        if needDB:
            self.db = self.master.db = fakedb.FakeDBConnector(self)
        self.ep = self.endpointClass(self.master)

        self.assertIsInstance(self.ep.pathPattern, tuple,
                "did you forget the ',' in a 1-element pathPattern?")
        self.path_args = set([
            arg.split(':', 1)[1] for arg in self.ep.pathPattern
            if ':' in arg ])

    def tearDownEndpoint(self):
        pass

    # call get/control, with extra checks

    def callGet(self, options, kwargs):
        self.assertEqual(set(kwargs), self.path_args)
        return self.ep.get(options, kwargs)

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
