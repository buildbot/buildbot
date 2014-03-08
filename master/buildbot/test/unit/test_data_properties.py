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

from buildbot.data import properties
from buildbot.test.fake import fakedb
from buildbot.test.util import endpoint
from twisted.trial import unittest


class BuildsetPropertiesEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = properties.BuildsetPropertiesEndpoint
    resourceTypeClass = properties.Properties

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Buildset(id=13, reason='because I said so'),
            fakedb.SourceStamp(id=92),
            fakedb.SourceStamp(id=93),
            fakedb.BuildsetSourceStamp(buildsetid=13, sourcestampid=92),
            fakedb.BuildsetSourceStamp(buildsetid=13, sourcestampid=93),

            fakedb.Buildset(id=14, reason='no sourcestamps'),

            fakedb.BuildsetProperty(buildsetid=14)
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get_properties(self):
        d = self.callGet(('buildsets', 14, 'properties'))

        @d.addCallback
        def check(props):
            self.assertEqual(props, {u'prop': (22, u'fakedb')})
        return d
