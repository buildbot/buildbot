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

from twisted.trial import unittest

from buildbot.data import sourcestamps
from buildbot.test.fake import fakedb
from buildbot.test.util import endpoint


class SourceStampEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = sourcestamps.SourceStampEndpoint
    resourceTypeClass = sourcestamps.SourceStamp

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.SourceStamp(id=13, branch=u'oak'),
            fakedb.Patch(id=99, patch_base64='aGVsbG8sIHdvcmxk',
                         patch_author='bar', patch_comment='foo', subdir='/foo',
                         patchlevel=3),
            fakedb.SourceStamp(id=14, patchid=99, branch=u'poplar'),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get_existing(self):
        d = self.callGet(('sourcestamps', 13))

        @d.addCallback
        def check(sourcestamp):
            self.validateData(sourcestamp)
            self.assertEqual(sourcestamp['branch'], u'oak')
            self.assertEqual(sourcestamp['patch'], None)
        return d

    def test_get_existing_patch(self):
        d = self.callGet(('sourcestamps', 14))

        @d.addCallback
        def check(sourcestamp):
            self.validateData(sourcestamp)
            self.assertEqual(sourcestamp['branch'], u'poplar')
            self.assertEqual(sourcestamp['patch'], {
                'patchid': 99,
                'author': u'bar',
                'body': b'hello, world',
                'comment': u'foo',
                'level': 3,
                'subdir': u'/foo',
            })
        return d

    def test_get_missing(self):
        d = self.callGet(('sourcestamps', 99))

        @d.addCallback
        def check(sourcestamp):
            self.assertEqual(sourcestamp, None)
        return d


class SourceStampsEndpoint(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = sourcestamps.SourceStampsEndpoint
    resourceTypeClass = sourcestamps.SourceStamp

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.SourceStamp(id=13),
            fakedb.SourceStamp(id=14),
        ])

    def tearDown(self):
        self.tearDownEndpoint()

    def test_get(self):
        d = self.callGet(('sourcestamps',))

        @d.addCallback
        def check(sourcestamps):
            [self.validateData(m) for m in sourcestamps]
            self.assertEqual(sorted([m['ssid'] for m in sourcestamps]),
                             [13, 14])
        return d


class SourceStamp(unittest.TestCase):

    pass
