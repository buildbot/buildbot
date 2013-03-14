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
from twisted.internet import defer
from buildbot.data import root, base
from buildbot.test.util import endpoint

class RootEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = root.RootEndpoint
    resourceTypeClass = root.Root

    def setUp(self):
        self.setUpEndpoint()
        self.master.data.rootLinks = [
            {'name': u'abc', 'link': base.Link(('abc',))},
        ]

    def tearDown(self):
        self.tearDownEndpoint()


    @defer.inlineCallbacks
    def test_get(self):
        rootlinks = yield self.callGet(dict(), dict())
        [ self.validateData(root) for root in rootlinks ]
        self.assertEqual(rootlinks, [
            {'name': u'abc', 'link': base.Link(('abc',))},
        ])
