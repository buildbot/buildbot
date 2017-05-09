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

import copy
import sys

from mock import Mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot import config
from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters.notifier import NotifierBase
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.notifier import NotifierTestMixin

py_27 = sys.version_info[0] > 2 or (sys.version_info[0] == 2
                                    and sys.version_info[1] >= 7)


class TestMailNotifier(ConfigErrorsMixin, unittest.TestCase, NotifierTestMixin):

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self,
                                             wantData=True, wantDb=True, wantMq=True)

    @defer.inlineCallbacks
    def setupNotifier(self, *args, **kwargs):
        mn = NotifierBase(*args, **kwargs)
        mn.sendMessage = Mock(spec=mn.sendMessage)
        mn.sendMessage.return_value = "<message>"
        yield mn.setServiceParent(self.master)
        yield mn.startService()
        defer.returnValue(mn)

    def test_init_enforces_tags_and_builders_are_mutually_exclusive(self):
        self.assertRaises(config.ConfigErrors, NotifierBase,
                          tags=['fast', 'slow'], builders=['a', 'b'])

    def test_init_warns_notifier_mode_all_in_iter(self):
        self.assertRaisesConfigError(
            "mode 'all' is not valid in an iterator and must be passed in as a separate string",
            lambda: NotifierBase(mode=['all']))

    @defer.inlineCallbacks
    def test_buildsetComplete_sends_message(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        mn = yield self.setupNotifier(buildSetSummary=True,
                                      mode=("failing", "passing", "warnings"),
                                      builders=["Builder1", "Builder2"])

        mn.buildMessage = Mock()
        yield mn.buildsetComplete('buildset.98.complete',
                                  dict(bsid=98))

        mn.buildMessage.assert_called_with(
            "whole buildset",
            builds, SUCCESS)
        self.assertEqual(mn.buildMessage.call_count, 1)

    @defer.inlineCallbacks
    def test_buildsetComplete_doesnt_send_message(self):
        _, builds = yield self.setupBuildResults(SUCCESS)
        # disable passing...
        mn = yield self.setupNotifier(buildSetSummary=True,
                                      mode=("failing", "warnings"),
                                      builders=["Builder1", "Builder2"])

        mn.buildMessage = Mock()
        yield mn.buildsetComplete('buildset.98.complete',
                                  dict(bsid=98))

        self.assertFalse(mn.buildMessage.called)

    @defer.inlineCallbacks
    def test_isMessageNeeded_ignores_unspecified_tags(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        build['builder']['tags'] = ['slow']
        mn = yield self.setupNotifier(tags=["fast"])
        self.assertFalse(mn.isMessageNeeded(build))

    @defer.inlineCallbacks
    def test_isMessageNeeded_tags(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        build['builder']['tags'] = ['fast']
        mn = yield self.setupNotifier(tags=["fast"])
        self.assertTrue(mn.isMessageNeeded(build))

    @defer.inlineCallbacks
    def test_isMessageNeeded_schedulers_sends_mail(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        mn = yield self.setupNotifier(schedulers=['checkin'])
        self.assertTrue(mn.isMessageNeeded(build))

    @defer.inlineCallbacks
    def test_isMessageNeeded_schedulers_doesnt_send_mail(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        mn = yield self.setupNotifier(schedulers=['some-random-scheduler'])
        self.assertFalse(mn.isMessageNeeded(build))

    @defer.inlineCallbacks
    def test_isMessageNeeded_branches_sends_mail(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        mn = yield self.setupNotifier(branches=['master'])
        self.assertTrue(mn.isMessageNeeded(build))

    @defer.inlineCallbacks
    def test_isMessageNeeded_branches_doesnt_send_mail(self):
        _, builds = yield self.setupBuildResults(SUCCESS)

        build = builds[0]
        # force tags
        mn = yield self.setupNotifier(branches=['some-random-branch'])
        self.assertFalse(mn.isMessageNeeded(build))

    @defer.inlineCallbacks
    def run_simple_test_sends_message_for_mode(self, mode, result, shouldSend=True):
        _, builds = yield self.setupBuildResults(result)

        mn = yield self.setupNotifier(mode=mode)

        self.assertEqual(mn.isMessageNeeded(builds[0]), shouldSend)

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

        mn = yield self.setupNotifier(mode=mode)

        build = builds[0]
        if results1 is not None:
            build['prev_build'] = copy.deepcopy(builds[0])
            build['prev_build']['results'] = results1
        else:
            build['prev_build'] = None
        self.assertEqual(mn.isMessageNeeded(builds[0]), shouldSend)

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
    def setupBuildMessage(self, **mnKwargs):

        _, builds = yield self.setupBuildResults(SUCCESS)

        mn = yield self.setupNotifier(**mnKwargs)

        mn.messageFormatter = Mock(spec=mn.messageFormatter)
        mn.messageFormatter.formatMessageForBuildResults.return_value = {"body": "body", "type": "text",
                                                                         "subject": "subject"}
        yield mn.buildMessage("mybldr", builds, SUCCESS)
        defer.returnValue((mn, builds))

    @defer.inlineCallbacks
    def test_buildMessage_nominal(self):
        mn, builds = yield self.setupBuildMessage(mode=("change",))

        build = builds[0]
        mn.messageFormatter.formatMessageForBuildResults.assert_called_with(
            ('change',), 'mybldr', build['buildset'], build, self.master,
            None, [u'me@foo'])

        self.assertEqual(mn.sendMessage.call_count, 1)
        mn.sendMessage.assert_called_with('body', 'subject', 'text', 'mybldr', SUCCESS, builds,
                                          [u'me@foo'], [], [])

    @defer.inlineCallbacks
    def test_buildMessage_addLogs(self):
        mn, builds = yield self.setupBuildMessage(mode=("change",), addLogs=True)
        self.assertEqual(mn.sendMessage.call_count, 1)
        # make sure the logs are send
        self.assertEqual(mn.sendMessage.call_args[0][8][0]['logid'], 60)
        # make sure the log has content
        self.assertIn(
            "log with", mn.sendMessage.call_args[0][8][0]['content']['content'])

    @defer.inlineCallbacks
    def test_buildMessage_addPatch(self):
        mn, builds = yield self.setupBuildMessage(mode=("change",), addPatch=True)
        self.assertEqual(mn.sendMessage.call_count, 1)
        # make sure the patch are sent
        self.assertEqual(mn.sendMessage.call_args[0][7],
                         [{'author': u'him@foo',
                           'body': b'hello, world',
                           'comment': u'foo',
                           'level': 3,
                           'patchid': 99,
                           'subdir': u'/foo'}])

    @defer.inlineCallbacks
    def test_buildMessage_addPatchNoPatch(self):
        SourceStamp = fakedb.SourceStamp

        class NoPatchSourcestamp(SourceStamp):

            def __init__(self, id, patchid):
                SourceStamp.__init__(self, id=id)
        self.patch(fakedb, 'SourceStamp', NoPatchSourcestamp)
        mn, builds = yield self.setupBuildMessage(mode=("change",), addPatch=True)
        self.assertEqual(mn.sendMessage.call_count, 1)
        # make sure no patches are sent
        self.assertEqual(mn.sendMessage.call_args[0][7], [])

    @defer.inlineCallbacks
    def test_workerMissingSendMessage(self):

        mn = yield self.setupNotifier(watchedWorkers=['myworker'])

        yield mn.workerMissing('worker.98.complete',
                               dict(name='myworker',
                                    notify=["workeradmin@example.org"],
                                    workerinfo=dict(admin="myadmin"),
                                    last_connection="yesterday"))

        self.assertEqual(mn.sendMessage.call_count, 1)
        text = mn.sendMessage.call_args[0][0]
        recipients = mn.sendMessage.call_args[1]['users']
        self.assertEqual(recipients, ['workeradmin@example.org'])
        self.assertIn(
            b"has noticed that the worker named myworker went away", text)
