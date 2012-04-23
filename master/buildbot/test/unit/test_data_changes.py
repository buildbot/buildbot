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
from buildbot.data import changes, exceptions
from buildbot.test.util import resourcetype, endpoint
from buildbot.test.fake import fakedb

class Change(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = changes.Change

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Change(changeid=13, branch=u'trunk', revision=u'9283',
                            repository=u'svn://...', codebase=u'cbsvn',
                            project=u'world-domination'),
        ])


    def tearDown(self):
        self.tearDownEndpoint()


    def test_get_existing(self):
        d = self.callGet(dict(), dict(changeid=13))
        @d.addCallback
        def check(change):
            resourcetype.verifyChange(self, change)
            self.assertEqual(change['project'], 'world-domination')
        return d


    def test_get_missing(self):
        d = self.callGet(dict(), dict(changeid=99))
        @d.addCallback
        def check(change):
            self.assertEqual(change, None)
        return d


class Changes(endpoint.EndpointMixin, unittest.TestCase):

    endpointClass = changes.Changes

    def setUp(self):
        self.setUpEndpoint()
        self.db.insertTestData([
            fakedb.Change(changeid=13, branch=u'trunk', revision=u'9283',
                            repository=u'svn://...', codebase=u'cbsvn',
                            project=u'world-domination'),
            fakedb.Change(changeid=14, branch=u'devel', revision=u'9284',
                            repository=u'svn://...', codebase=u'cbsvn',
                            project=u'world-domination'),
        ])


    def tearDown(self):
        self.tearDownEndpoint()


    def test_get(self):
        d = self.callGet(dict(), dict())
        @d.addCallback
        def check(changes):
            resourcetype.verifyChange(self, changes[0])
            self.assertEqual(changes[0]['changeid'], 13)
            resourcetype.verifyChange(self, changes[1])
            self.assertEqual(changes[1]['changeid'], 14)
        return d

    def test_get_fewer(self):
        d = self.callGet(dict(count='1'), dict())
        @d.addCallback
        def check(changes):
            self.assertEqual(len(changes), 1)
            resourcetype.verifyChange(self, changes[0])
        return d

    def test_get_invalid_count(self):
        d = self.callGet(dict(count='ten'), dict())
        self.assertFailure(d, exceptions.InvalidOptionException)
