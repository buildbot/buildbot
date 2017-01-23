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
from twisted.trial import unittest

from buildbot.data import connector
from buildbot.data import root
from buildbot.test.util import endpoint


class RootEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = root.RootEndpoint
    resourceTypeClass = root.Root

    def setUp(self):
        self.setUpEndpoint()
        self.master.data.rootLinks = [
            {'name': u'abc'},
        ]

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get(self):
        rootlinks = yield self.callGet(('',))
        [self.validateData(root) for root in rootlinks]
        self.assertEqual(rootlinks, [
            {'name': u'abc'},
        ])


class SpecEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = root.SpecEndpoint
    resourceTypeClass = root.Spec

    def setUp(self):
        self.setUpEndpoint()
        # replace fakeConnector with real DataConnector
        self.master.data.disownServiceParent()
        self.master.data = connector.DataConnector()
        self.master.data.setServiceParent(self.master)

    def tearDown(self):
        self.tearDownEndpoint()

    @defer.inlineCallbacks
    def test_get(self):
        specs = yield self.callGet(('application.spec',))
        [self.validateData(s) for s in specs]
        for s in specs:
            # only test an endpoint that is reasonably stable
            if s['path'] != "master":
                continue
            self.assertEqual(s,
                             {'path': 'master',
                              'type': 'master',
                              'type_spec': {'fields': [{'name': 'active',
                                                        'type': 'boolean',
                                                        'type_spec': {'name': 'boolean'}},
                                                       {'name': 'masterid',
                                                        'type': 'integer',
                                                        'type_spec': {'name': 'integer'}},
                                                       {'name': 'link',
                                                        'type': 'link',
                                                        'type_spec': {'name': 'link'}},
                                                       {'name': 'name',
                                                        'type': 'string',
                                                        'type_spec': {'name': 'string'}},
                                                       {'name': 'last_active',
                                                        'type': 'datetime',
                                                        'type_spec': {'name': 'datetime'}}],
                                            'type': 'master'},
                              'plural': 'masters'})
