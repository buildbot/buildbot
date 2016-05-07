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
# Copyright 2011 Louis Opter <kalessin@kalessin.fr>
#
# Written from the github change hook unit test
import StringIO

from twisted.trial import unittest

import buildbot.www.change_hook as change_hook
from buildbot.test.fake.web import FakeRequest
from buildbot.test.fake.web import fakeMasterForHooks

# Sample Google Code commit payload extracted from a Google Code test project
# {
#     "repository_path": "https://code.google.com/p/webhook-test/",
#     "project_name": "webhook-test",
#     "revision_count": 1,
#     "revisions": [
#         {
#             "added": [],
#             "parents": ["6574485e26a09a0e743e0745374056891d6a836a"],
#             "author": "Louis Opter \\u003Clouis@lse.epitech.net\\u003E",
#             "url": "http://webhook-test.googlecode.com/hg-history/68e5df283a8e751cdbf95516b20357b2c46f93d4/",
#             "timestamp": 1324082130,
#             "message": "Print a message",
#             "path_count": 1,
#             "removed": [],
#             "modified": ["/CMakeLists.txt"],
#             "revision": "68e5df283a8e751cdbf95516b20357b2c46f93d4"
#         }
#     ]
# }
googleCodeJsonBody = r'{"repository_path":"https://code.google.com/p/webhook-test/","project_name":"webhook-test","revisions":[{"added":[],"parents":["6574485e26a09a0e743e0745374056891d6a836a"],"author":"Louis Opter \u003Clouis@lse.epitech.net\u003E","url":"http://webhook-test.googlecode.com/hg-history/68e5df283a8e751cdbf95516b20357b2c46f93d4/","timestamp":1324082130,"message":"Print a message","path_count":1,"removed":[],"modified":["/CMakeLists.txt"],"revision":"68e5df283a8e751cdbf95516b20357b2c46f93d4"}],"revision_count":1}'


class TestChangeHookConfiguredWithGoogleCodeChange(unittest.TestCase):

    def setUp(self):
        self.request = FakeRequest()
        # Google Code simply transmit the payload as an UTF-8 JSON body
        self.request.content = StringIO.StringIO(googleCodeJsonBody)
        self.request.received_headers = {
            'Google-Code-Project-Hosting-Hook-Hmac': '85910bf93ba5c266402d9328b0c7a856',
            'Content-Length': '509',
            'Accept-Encoding': 'gzip',
            'User-Agent': 'Google Code Project Hosting (+http://code.google.com/p/support/wiki/PostCommitWebHooks)',
            'Host': 'buildbot6-lopter.dotcloud.com:19457',
            'Content-Type': 'application/json; charset=UTF-8'
        }

        self.changeHook = change_hook.ChangeHookResource(dialects={
            'googlecode': {
                'secret_key': 'FSP3p-Ghdn4T0oqX',
                'branch': 'test'
            }
        }, master=fakeMasterForHooks())

    # Test 'base' hook with attributes. We should get a json string representing
    # a Change object as a dictionary. All values show be set.
    def testGoogleCodeWithHgChange(self):
        self.request.uri = "/change_hook/googlecode"
        self.request.method = "GET"
        d = self.request.test_render(self.changeHook)

        def check_changes(r):
            # Only one changeset has been submitted.
            self.assertEquals(len(self.changeHook.master.addedChanges), 1)

            # First changeset.
            change = self.changeHook.master.addedChanges[0]
            self.assertEquals(change['files'], ['/CMakeLists.txt'])
            self.assertEquals(
                change["repository"], "https://code.google.com/p/webhook-test/")
            self.assertEquals(change["when"], 1324082130)
            self.assertEquals(
                change["author"], "Louis Opter <louis@lse.epitech.net>")
            self.assertEquals(
                change["revision"], '68e5df283a8e751cdbf95516b20357b2c46f93d4')
            self.assertEquals(change["comments"], "Print a message")
            self.assertEquals(change["branch"], "test")
            self.assertEquals(change[
                              "revlink"], "http://webhook-test.googlecode.com/hg-history/68e5df283a8e751cdbf95516b20357b2c46f93d4/")

        d.addCallback(check_changes)
        return d
