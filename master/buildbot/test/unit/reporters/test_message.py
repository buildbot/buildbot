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

import textwrap

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import RETRY
from buildbot.process.results import SKIPPED
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters import message
from buildbot.reporters import utils
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util.misc import TestReactorMixin


class TestMessageFormatting(unittest.TestCase):
    def test_get_detected_status_text_failure(self):
        self.assertEqual(message.get_detected_status_text(['change'], FAILURE, FAILURE),
                         'failed build')
        self.assertEqual(message.get_detected_status_text(['change'], FAILURE, SUCCESS),
                         'new failure')
        self.assertEqual(message.get_detected_status_text(['change'], FAILURE, None),
                         'failed build')
        self.assertEqual(message.get_detected_status_text(['problem'], FAILURE, FAILURE),
                         'failed build')
        self.assertEqual(message.get_detected_status_text(['problem'], FAILURE, SUCCESS),
                         'new failure')
        self.assertEqual(message.get_detected_status_text(['problem'], FAILURE, None),
                         'failed build')

    def test_get_detected_status_text_warnings(self):
        self.assertEqual(message.get_detected_status_text(['change'], WARNINGS, SUCCESS),
                         'problem in the build')
        self.assertEqual(message.get_detected_status_text(['change'], WARNINGS, None),
                         'problem in the build')

    def test_get_detected_status_text_success(self):
        self.assertEqual(message.get_detected_status_text(['change'], SUCCESS, FAILURE),
                         'restored build')
        self.assertEqual(message.get_detected_status_text(['change'], SUCCESS, SUCCESS),
                         'passing build')
        self.assertEqual(message.get_detected_status_text(['change'], SUCCESS, None),
                         'passing build')

        self.assertEqual(message.get_detected_status_text(['problem'], SUCCESS, FAILURE),
                         'passing build')
        self.assertEqual(message.get_detected_status_text(['problem'], SUCCESS, SUCCESS),
                         'passing build')
        self.assertEqual(message.get_detected_status_text(['problem'], SUCCESS, None),
                         'passing build')

    def test_get_detected_status_text_exception(self):
        self.assertEqual(message.get_detected_status_text(['problem'], EXCEPTION, FAILURE),
                         'build exception')
        self.assertEqual(message.get_detected_status_text(['problem'], EXCEPTION, SUCCESS),
                         'build exception')
        self.assertEqual(message.get_detected_status_text(['problem'], EXCEPTION, None),
                         'build exception')

    def test_get_detected_status_text_other(self):
        self.assertEqual(message.get_detected_status_text(['problem'], SKIPPED, None),
                         'skipped build')
        self.assertEqual(message.get_detected_status_text(['problem'], RETRY, None),
                         'retry build')
        self.assertEqual(message.get_detected_status_text(['problem'], CANCELLED, None),
                         'cancelled build')

    def test_get_message_summary_text_success(self):
        self.assertEqual(message.get_message_summary_text({'state_string': 'mywarning'}, SUCCESS),
                         'Build succeeded!')

    def test_get_message_summary_text_warnings(self):
        self.assertEqual(message.get_message_summary_text({'state_string': 'mywarning'}, WARNINGS),
                         'Build Had Warnings: mywarning')
        self.assertEqual(message.get_message_summary_text({'state_string': None}, WARNINGS),
                         'Build Had Warnings')

    def test_get_message_summary_text_cancelled(self):
        self.assertEqual(message.get_message_summary_text({'state_string': 'mywarning'}, CANCELLED),
                         'Build was cancelled')

    def test_get_message_summary_text_skipped(self):
        self.assertEqual(message.get_message_summary_text({'state_string': 'mywarning'}, SKIPPED),
                         'BUILD FAILED: mywarning')
        self.assertEqual(message.get_message_summary_text({'state_string': None}, SKIPPED),
                         'BUILD FAILED')

    def test_get_message_source_stamp_text_empty(self):
        self.assertEqual(message.get_message_source_stamp_text([]), '')

    def test_get_message_source_stamp_text_multiple(self):
        stamps = [
            {'codebase': 'a', 'branch': None, 'revision': None, 'patch': None},
            {'codebase': 'b', 'branch': None, 'revision': None, 'patch': None},
        ]
        self.assertEqual(message.get_message_source_stamp_text(stamps),
                         "Build Source Stamp 'a': HEAD\n"
                         "Build Source Stamp 'b': HEAD\n")

    def test_get_message_source_stamp_text_with_props(self):
        stamps = [
            {'codebase': 'a', 'branch': 'br', 'revision': 'abc', 'patch': 'patch'}
        ]
        self.assertEqual(message.get_message_source_stamp_text(stamps),
                         "Build Source Stamp 'a': [branch br] abc (plus patch)\n")


class TestMessage(TestReactorMixin, unittest.TestCase):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

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
                         masterid=92, results=results2),
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
        self.setupDb(lastresults, results)
        res = yield utils.getDetailsForBuildset(self.master, 99, wantProperties=True,
                                                wantPreviousBuild=True)
        build = res['builds'][0]
        res = yield self.message.format_message_for_build(mode, "Builder1", build, self.master,
                                                          ["him@bar", "me@foo"])
        return res

    @defer.inlineCallbacks
    def test_message_success(self):
        res = yield self.doOneTest(SUCCESS, SUCCESS)
        self.assertEqual(res['type'], "plain")
        self.assertEqual(res['body'], textwrap.dedent('''\
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
        self.assertIsNone(res['subject'])

    @defer.inlineCallbacks
    def test_inline_template(self):
        self.message = message.MessageFormatter(template="URL: {{ build_url }} -- {{ summary }}")
        res = yield self.doOneTest(SUCCESS, SUCCESS)
        self.assertEqual(res['type'], "plain")
        self.assertEqual(res['body'],
                         "URL: http://localhost:8080/#builders/80/builds/1 -- Build succeeded!")

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
