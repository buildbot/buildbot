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

import textwrap

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters import message
from buildbot.reporters import utils
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster


class TestMessage(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)

        self.message = message.MessageFormatter()
        self.messageMissing = message.MessageFormatterMissingWorker()

    def setupDb(self, results1, results2):

        self.db = self.master.db
        self.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Worker(id=13, name='wrkr'),
            fakedb.Buildset(id=98, results=results1, reason="testReason1"),
            fakedb.Buildset(id=99, results=results2, reason="testReason2"),
            fakedb.Builder(id=80, name='Builder1'),
            fakedb.BuildRequest(id=11, buildsetid=98, builderid=80),
            fakedb.BuildRequest(id=12, buildsetid=99, builderid=80),
            fakedb.Build(id=20, number=0, builderid=80, buildrequestid=11, workerid=13,
                         masterid=92, results=results1),
            fakedb.Build(id=21, number=1, builderid=80, buildrequestid=12, workerid=13,
                         masterid=92, results=results1),
        ])
        for _id in (20, 21):
            self.db.insertTestData([
                fakedb.BuildProperty(
                    buildid=_id, name="workername", value="wrkr"),
                fakedb.BuildProperty(
                    buildid=_id, name="reason", value="because"),
            ])

    @defer.inlineCallbacks
    def doOneTest(self, lastresults, results, mode="all"):
        self.setupDb(results, lastresults)
        res = yield utils.getDetailsForBuildset(self.master, 99, wantProperties=True)
        build = res['builds'][0]
        buildset = res['buildset']
        res = yield self.message.formatMessageForBuildResults(
            mode, "Builder1", buildset, build, self.master,
            lastresults, ["him@bar", "me@foo"])
        defer.returnValue(res)

    @defer.inlineCallbacks
    def test_message_success(self):
        res = yield self.doOneTest(SUCCESS, SUCCESS)
        self.assertEqual(res['type'], "plain")
        self.assertEqual(res['body'], textwrap.dedent(u'''\
            The Buildbot has detected a passing build on builder Builder1 while building Buildbot.
            Full details are available at:
                http://localhost:8080/#builders/80/builds/1

            Buildbot URL: http://localhost:8080/

            Worker for this Build: wrkr

            Build Reason: because
            Blamelist: him@bar, me@foo

            Build succeeded!

            Sincerely,
             -The Buildbot'''))
        self.assertTrue('subject' not in res)

    @defer.inlineCallbacks
    def test_inline_template(self):
        self.message = message.MessageFormatter(template="URL: {{ build_url }} -- {{ summary }}")
        res = yield self.doOneTest(SUCCESS, SUCCESS)
        self.assertEqual(res['type'], "plain")
        self.assertEqual(res['body'], "URL: http://localhost:8080/#builders/80/builds/1 -- Build succeeded!")

    @defer.inlineCallbacks
    def test_inline_subject(self):
        self.message = message.MessageFormatter(subject="subject")
        res = yield self.doOneTest(SUCCESS, SUCCESS)
        self.assertEqual(res['subject'], "subject")

    @defer.inlineCallbacks
    def test_message_failure(self):
        res = yield self.doOneTest(SUCCESS, FAILURE)
        self.assertIn(
            "The Buildbot has detected a failed build on builder", res['body'])

    @defer.inlineCallbacks
    def test_message_failure_change(self):
        res = yield self.doOneTest(SUCCESS, FAILURE, "change")
        self.assertIn(
            "The Buildbot has detected a new failure on builder", res['body'])

    @defer.inlineCallbacks
    def test_message_success_change(self):
        res = yield self.doOneTest(FAILURE, SUCCESS, "change")
        self.assertIn(
            "The Buildbot has detected a restored build on builder", res['body'])

    @defer.inlineCallbacks
    def test_message_success_nochange(self):
        res = yield self.doOneTest(SUCCESS, SUCCESS, "change")
        self.assertIn(
            "The Buildbot has detected a passing build on builder", res['body'])

    @defer.inlineCallbacks
    def test_message_failure_nochange(self):
        res = yield self.doOneTest(FAILURE, FAILURE, "change")
        self.assertIn(
            "The Buildbot has detected a failed build on builder", res['body'])

    @defer.inlineCallbacks
    def test_missing_worker(self):
        self.setupDb(SUCCESS, SUCCESS)
        workers = yield self.master.data.get(('workers',))
        worker = workers[0]
        worker['notify'] = ['e@mail']
        worker['last_connection'] = ['yesterday']
        res = yield self.messageMissing.formatMessageForMissingWorker(self.master, worker)
        text = res['body']
        self.assertIn("has noticed that the worker named wrkr went away", text)
