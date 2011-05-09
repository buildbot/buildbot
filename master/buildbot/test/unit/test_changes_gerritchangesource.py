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
# this program; if not, write to the Free Software Foundation, Inc[''], 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from twisted.trial import unittest
from buildbot.util import json
from buildbot.test.util import changesource
from buildbot.changes import gerritchangesource

class TestGerritChangeSource(changesource.ChangeSourceMixin,
                             unittest.TestCase):

    def setUp(self):
        return self.setUpChangeSource()

    def tearDown(self):
        return self.tearDownChangeSource()

    def newChangeSource(self, host, user):
        s = gerritchangesource.GerritChangeSource(host, user)
        self.attachChangeSource(s)
        return s

    # tests

    def test_describe(self):
        s = self.newChangeSource('somehost', 'someuser')
        self.assertSubstring("GerritChangeSource", s.describe())

    # TODO: test the backoff algorithm

    def test_lineReceived_patchset_created(self):
        s = self.newChangeSource('somehost', 'someuser')
        d = s.lineReceived(json.dumps(dict(
            type="patchset-created",
            change=dict(
                branch="br",
                project="pr",
                owner=dict(name="Dustin", email="dustin@mozilla.com"),
                url="http://buildbot.net",
                subject="fix 1234"
            ),
            patchSet=dict(revision="abcdef")
        )))

        def check(_):
            self.failUnlessEqual(len(self.changes_added), 1)
            c = self.changes_added[0]
            self.assertEqual(c['author'], "Dustin <dustin@mozilla.com>")
            self.assertEqual(c['project'], "pr")
            self.assertEqual(c['branch'], "br")
            self.assertEqual(c['revision'], "abcdef")
            self.assertEqual(c['revlink'], "http://buildbot.net")
            self.assertEqual(c['comments'], "fix 1234")
            self.assertEqual(c['files'], [ 'unknown' ])
            self.assertEqual(c['properties']['event.change.subject'], 'fix 1234')
        d.addCallback(check)
        return d
