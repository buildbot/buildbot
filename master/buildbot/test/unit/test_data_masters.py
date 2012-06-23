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

from twisted.trial import unittest
from buildbot.data import masters
from buildbot.test.util import types, endpoint
from buildbot.test.fake import fakemaster

class Master(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = masters.MasterEndpoint

    def setUp(self):
        self.setUpEndpoint()
        self.master.master_name = "myname"


    def tearDown(self):
        self.tearDownEndpoint()


    def test_get_existing(self):
        d = self.callGet(dict(), dict(masterid=1))
        @d.addCallback
        def check(master):
            types.verifyData(self, 'master', {}, master)
            self.assertEqual(master['name'], 'myname')
        return d


    def test_get_missing(self):
        d = self.callGet(dict(), dict(masterid=99))
        @d.addCallback
        def check(master):
            self.assertEqual(master, None)
        return d


class Masters(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = masters.MastersEndpoint

    def setUp(self):
        self.setUpEndpoint()
        self.master.master_name = "myname"


    def tearDown(self):
        self.tearDownEndpoint()


    def test_get(self):
        d = self.callGet(dict(), dict())
        @d.addCallback
        def check(masters):
            types.verifyData(self, 'master', {}, masters[0])
            self.assertEqual(masters[0]['masterid'], 1)
        return d


class MasterResourceType(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(wantMq=True, wantDb=True,
                                                testcase=self)
        self.rtype = masters.MasterResourceType(self.master)

