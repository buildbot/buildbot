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

import base64
import copy
import sys

from mock import Mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.config import ConfigErrors
from buildbot.process import properties
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters import utils
from buildbot.reporters.pushover import PushoverNotifier
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.fake import httpclientservice as fakehttpclientservice
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.util import bytes2unicode
from buildbot.util import ssl

py_27 = sys.version_info[0] > 2 or (sys.version_info[0] == 2
                                    and sys.version_info[1] >= 7)


class TestPushoverNotifier(ConfigErrorsMixin, unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)
        self._http = self.successResultOf(fakehttpclientservice.HTTPClientService.getFakeService(
            self.master, self, 'https://api.pushover.net'))

    @defer.inlineCallbacks
    def setupBuildResults(self, results, wantPreviousBuild=False):
        # this testsuite always goes through setupBuildResults so that
        # the data is sure to be the real data schema known coming from data
        # api

        self.db = self.master.db
        self.db.insertTestData([
            fakedb.Master(id=92),
            fakedb.Worker(id=13, name='wrk'),
            fakedb.Buildset(id=98, results=results, reason="testReason1"),
            fakedb.Builder(id=80, name='Builder1'),
            fakedb.BuildRequest(id=11, buildsetid=98, builderid=80),
            fakedb.Build(id=20, number=0, builderid=80, buildrequestid=11, workerid=13,
                         masterid=92, results=results),
            fakedb.Step(id=50, buildid=20, number=5, name='make'),
            fakedb.BuildsetSourceStamp(buildsetid=98, sourcestampid=234),
            fakedb.SourceStamp(id=234, patchid=99),
            fakedb.Change(changeid=13, branch=u'trunk', revision=u'9283', author='me@foo',
                          repository=u'svn://...', codebase=u'cbsvn',
                          project=u'world-domination', sourcestampid=234),
            fakedb.Log(id=60, stepid=50, name='stdio', slug='stdio', type='s',
                       num_lines=7),
            fakedb.LogChunk(logid=60, first_line=0, last_line=1, compressed=0,
                            content=u'Unicode log with non-ascii (\u00E5\u00E4\u00F6).'),
            fakedb.Patch(id=99, patch_base64='aGVsbG8sIHdvcmxk',
                         patch_author='him@foo', patch_comment='foo', subdir='/foo',
                         patchlevel=3),
        ])
        for _id in (20,):
            self.db.insertTestData([
                fakedb.BuildProperty(
                    buildid=_id, name="workername", value="wrk"),
                fakedb.BuildProperty(
                    buildid=_id, name="reason", value="because"),
                fakedb.BuildProperty(
                    buildid=_id, name="scheduler", value="checkin"),
                fakedb.BuildProperty(
                    buildid=_id, name="branch", value="master"),
            ])
        res = yield utils.getDetailsForBuildset(self.master, 98, wantProperties=True,
                                                wantPreviousBuild=wantPreviousBuild)
        builds = res['builds']
        buildset = res['buildset']

        @defer.inlineCallbacks
        def getChangesForBuild(buildid):
            assert buildid == 20
            ch = yield self.master.db.changes.getChange(13)
            defer.returnValue([ch])

        self.master.db.changes.getChangesForBuild = getChangesForBuild
        defer.returnValue((buildset, builds))

    @defer.inlineCallbacks
    def setupPushoverNotifier(self, *args, **kwargs):
        pn = PushoverNotifier(*args, **kwargs)
        yield pn.setServiceParent(self.master)
        yield pn.startService()
        defer.returnValue(pn)

    @defer.inlineCallbacks
    def test_SendMessage(self):
        pn = yield self.setupPushoverNotifier(user_key="1234", api_token="abcd",
                                              otherParams={'sound': "silent"})
        self._http.expect("post", "/1/messages.json",
                          params={'user': "1234", 'token': "abcd",
                                  'sound': "silent", 'message': "Test"},
                          content_json={'status': 1, 'request': '98765'})
        n = yield pn.sendMessage({'message': "Test"})
        j = yield n.json()
        self.assertEqual(j['status'], 1)
        self.assertEqual(j['request'], '98765')

    def test_init_enforces_tags_and_builders_are_mutually_exclusive(self):
        self.assertRaises(config.ConfigErrors,
                          PushoverNotifier, '1234', 'abcd',
                          tags=['fast', 'slow'], builders=['a', 'b'])

    def test_init_warns_notifier_mode_all_in_iter(self):
        self.assertRaisesConfigError(
            "mode 'all' is not valid in an iterator and must be passed in as a separate string",
            lambda: PushoverNotifier('1234', 'abcd', mode=['all']))

    @defer.inlineCallbacks
    def test_buildsetComplete_sends_message(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        pn = yield self.setupPushoverNotifier('1234', 'abcd',
                                          buildSetSummary=True,
                                          mode=(
                                              "failing", "passing", "warnings"),
                                          builders=["Builder1", "Builder2"])

        pn.buildMessage = Mock()
        yield pn.buildsetComplete('buildset.98.complete',
                                  dict(bsid=98))

        pn.buildMessage.assert_called_with(
            "whole buildset",
            builds, SUCCESS)
        self.assertEqual(pn.buildMessage.call_count, 1)

    @defer.inlineCallbacks
    def test_buildsetComplete_doesnt_send_message(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        # disable passing...
        pn = yield self.setupPushoverNotifier('1234', 'abcd',
                                          buildSetSummary=True,
                                          mode=("failing", "warnings"),
                                          builders=["Builder1", "Builder2"])

        pn.buildMessage = Mock()
        yield pn.buildsetComplete('buildset.98.complete',
                                  dict(bsid=98))

        self.assertFalse(pn.buildMessage.called)

    @defer.inlineCallbacks
    def test_isMessageNeeded_ignores_unspecified_tags(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        build['builder']['tags'] = ['slow']
        pn = yield self.setupPushoverNotifier('1234', 'abcd',
                                          tags=["fast"])
        self.assertFalse(pn.isMessageNeeded(build))

    @defer.inlineCallbacks
    def test_isMessageNeeded_tags(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        build['builder']['tags'] = ['fast']
        pn = yield self.setupPushoverNotifier('1234', 'abcd',
                                          tags=["fast"])
        self.assertTrue(pn.isMessageNeeded(build))

    @defer.inlineCallbacks
    def test_isMessageNeeded_schedulers_notifies(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        pn = yield self.setupPushoverNotifier('1234', 'abcd',
                                          schedulers=['checkin'])
        self.assertTrue(pn.isMessageNeeded(build))

    @defer.inlineCallbacks
    def test_isMessageNeeded_schedulers_doesnt_notify(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        pn = yield self.setupPushoverNotifier('1234', 'abcd',
                                          schedulers=['some-random-scheduler'])
        self.assertFalse(pn.isMessageNeeded(build))

    @defer.inlineCallbacks
    def test_isMessageNeeded_branches_notifies(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        pn = yield self.setupPushoverNotifier('1234', 'abcd',
                                          branches=['master'])
        self.assertTrue(pn.isMessageNeeded(build))

    @defer.inlineCallbacks
    def test_isMessageNeeded_branches_doesnt_notify(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        pn = yield self.setupPushoverNotifier('1234', 'abcd',
                                          branches=['some-random-branch'])
        self.assertFalse(pn.isMessageNeeded(build))

    @defer.inlineCallbacks
    def run_simple_test_sends_message_for_mode(self, mode, result, shouldSend=True):
        _, builds = yield self.setupBuildResults(result)

        pn = yield self.setupPushoverNotifier('1234', 'abcd', mode=mode)

        self.assertEqual(pn.isMessageNeeded(builds[0]), shouldSend)

    def run_simple_test_ignores_message_for_mode(self, mode, result):
        return self.run_simple_test_sends_message_for_mode(mode, result, False)

    def test_isMessageNeeded_mode_all_for_success(self):
        return self.run_simple_test_sends_message_for_mode("all", SUCCESS)

    def test_isMessageNeeded_mode_all_for_failure(self):
        return self.run_simple_test_sends_message_for_mode("all", FAILURE)

    def test_isMessageNeeded_mode_all_for_warnings(self):
        return self.run_simple_test_sends_message_for_mode("all", WARNINGS)

    def test_isMessageNeeded_mode_all_for_exception(self):
        return self.run_simple_test_sends_message_for_mode("all", EXCEPTION)

    def test_isMessageNeeded_mode_all_for_cancelled(self):
        return self.run_simple_test_sends_message_for_mode("all", CANCELLED)

    def test_isMessageNeeded_mode_failing_for_success(self):
        return self.run_simple_test_ignores_message_for_mode("failing", SUCCESS)

    def test_isMessageNeeded_mode_failing_for_failure(self):
        return self.run_simple_test_sends_message_for_mode("failing", FAILURE)

    def test_isMessageNeeded_mode_failing_for_warnings(self):
        return self.run_simple_test_ignores_message_for_mode("failing", WARNINGS)

    def test_isMessageNeeded_mode_failing_for_exception(self):
        return self.run_simple_test_ignores_message_for_mode("failing", EXCEPTION)

    def test_isMessageNeeded_mode_exception_for_success(self):
        return self.run_simple_test_ignores_message_for_mode("exception", SUCCESS)

    def test_isMessageNeeded_mode_exception_for_failure(self):
        return self.run_simple_test_ignores_message_for_mode("exception", FAILURE)

    def test_isMessageNeeded_mode_exception_for_warnings(self):
        return self.run_simple_test_ignores_message_for_mode("exception", WARNINGS)

    def test_isMessageNeeded_mode_exception_for_exception(self):
        return self.run_simple_test_sends_message_for_mode("exception", EXCEPTION)

    def test_isMessageNeeded_mode_warnings_for_success(self):
        return self.run_simple_test_ignores_message_for_mode("warnings", SUCCESS)

    def test_isMessageNeeded_mode_warnings_for_failure(self):
        return self.run_simple_test_sends_message_for_mode("warnings", FAILURE)

    def test_isMessageNeeded_mode_warnings_for_warnings(self):
        return self.run_simple_test_sends_message_for_mode("warnings", WARNINGS)

    def test_isMessageNeeded_mode_warnings_for_exception(self):
        return self.run_simple_test_ignores_message_for_mode("warnings", EXCEPTION)

    def test_isMessageNeeded_mode_passing_for_success(self):
        return self.run_simple_test_sends_message_for_mode("passing", SUCCESS)

    def test_isMessageNeeded_mode_passing_for_failure(self):
        return self.run_simple_test_ignores_message_for_mode("passing", FAILURE)

    def test_isMessageNeeded_mode_passing_for_warnings(self):
        return self.run_simple_test_ignores_message_for_mode("passing", WARNINGS)

    def test_isMessageNeeded_mode_passing_for_exception(self):
        return self.run_simple_test_ignores_message_for_mode("passing", EXCEPTION)

    @defer.inlineCallbacks
    def run_sends_message_for_problems(self, mode, results1, results2, shouldSend=True):
        _, builds = yield self.setupBuildResults(results2)

        pn = yield self.setupPushoverNotifier('1234', 'abcd', mode=mode)

        build = builds[0]
        if results1 is not None:
            build['prev_build'] = copy.deepcopy(builds[0])
            build['prev_build']['results'] = results1
        else:
            build['prev_build'] = None
        self.assertEqual(pn.isMessageNeeded(builds[0]), shouldSend)

    def test_isMessageNeeded_mode_problem_sends_on_problem(self):
        return self.run_sends_message_for_problems("problem", SUCCESS, FAILURE, True)

    def test_isMessageNeeded_mode_problem_ignores_successful_build(self):
        return self.run_sends_message_for_problems("problem", SUCCESS, SUCCESS, False)

    def test_isMessageNeeded_mode_problem_ignores_two_failed_builds_in_sequence(self):
        return self.run_sends_message_for_problems("problem", FAILURE, FAILURE, False)

    def test_isMessageNeeded_mode_change_sends_on_change(self):
        return self.run_sends_message_for_problems("change", FAILURE, SUCCESS, True)

    def test_isMessageNeeded_mode_change_sends_on_failure(self):
        return self.run_sends_message_for_problems("change", SUCCESS, FAILURE, True)

    def test_isMessageNeeded_mode_change_ignores_first_build(self):
        return self.run_sends_message_for_problems("change", None, FAILURE, False)

    def test_isMessageNeeded_mode_change_ignores_first_build2(self):
        return self.run_sends_message_for_problems("change", None, SUCCESS, False)

    def test_isMessageNeeded_mode_change_ignores_same_result_in_sequence(self):
        return self.run_sends_message_for_problems("change", SUCCESS, SUCCESS, False)

    def test_isMessageNeeded_mode_change_ignores_same_result_in_sequence2(self):
        return self.run_sends_message_for_problems("change", FAILURE, FAILURE, False)

    @defer.inlineCallbacks
    def test_BuildMessage(self):

        _, builds = yield self.setupBuildResults(SUCCESS)

        pn = yield self.setupPushoverNotifier('1234', 'abcd', mode=('change',), priorities={'passing': 1})

        pn.messageFormatter = Mock(spec=pn.messageFormatter)
        pn.messageFormatter.formatMessageForBuildResults.return_value = {"body": "body", "type": "plain",
                                                                         "subject": "subject"}

        pn.sendMessage = Mock(spec=pn.sendMessage)
        pn.sendMessage.return_value = '<notification>'

        yield pn.buildMessage("mybldr", builds, SUCCESS)

        build = builds[0]
        pn.messageFormatter.formatMessageForBuildResults.assert_called_with(
            ('change',), 'mybldr', build['buildset'], build, self.master,
            None, [u'me@foo'])

        pn.sendMessage.assert_called_with(dict(message='body', title='subject', priority=1))
        self.assertEqual(pn.sendMessage.call_count, 1)

    @defer.inlineCallbacks
    def test_workerMissingSendMessage(self):

        pn = yield self.setupPushoverNotifier('1234', 'abcd', priorities={'worker_missing': 2},
                                              watchedWorkers=['myworker'])

        pn.sendMessage = Mock()
        yield pn.workerMissing('worker.98.complete',
                               dict(name='myworker',
                                    workerinfo=dict(admin="myadmin"),
                                    last_connection="yesterday"))

        message = pn.sendMessage.call_args[0][0]['message']
        priority = pn.sendMessage.call_args[0][0]['priority']
        self.assertEqual(priority, 2)
        self.assertIn(b"has noticed that the worker named myworker went away", message)
