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


import copy

from parameterized import parameterized

from mock import Mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters import utils
from buildbot.reporters.generators.build import BuildStartEndStatusGenerator
from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.test.fake import fakemaster
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.util.reporter import ReporterTestMixin


class TestBuildGenerator(ConfigErrorsMixin, TestReactorMixin,
                         unittest.TestCase, ReporterTestMixin):

    def setUp(self):
        self.setUpTestReactor()
        self.setup_reporter_test()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

    @defer.inlineCallbacks
    def insert_build_finished_get_props(self, results, **kwargs):
        build = yield self.insert_build_finished(results, **kwargs)
        yield utils.getDetailsForBuild(self.master, build, wantProperties=True)
        return build

    @parameterized.expand([
        ('tags', 'tag'),
        ('tags', 1),
        ('builders', 'builder'),
        ('builders', 1),
        ('schedulers', 'scheduler'),
        ('schedulers', 1),
        ('branches', 'branch'),
        ('branches', 1),
    ])
    def test_list_params_check_raises(self, arg_name, arg_value):
        kwargs = {arg_name: arg_value}
        g = BuildStatusGenerator(**kwargs)
        with self.assertRaisesConfigError('must be a list or None'):
            g.check()

    def test_subject_newlines_not_allowed(self):
        g = BuildStatusGenerator(subject='subject\nwith\nnewline')
        with self.assertRaisesConfigError('Newlines are not allowed'):
            g.check()

    @defer.inlineCallbacks
    def test_is_message_needed_ignores_unspecified_tags(self):
        build = yield self.insert_build_finished_get_props(SUCCESS)

        # force tags
        build['builder']['tags'] = ['slow']
        g = BuildStatusGenerator(tags=["fast"])
        self.assertFalse(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_tags(self):
        build = yield self.insert_build_finished_get_props(SUCCESS)

        # force tags
        build['builder']['tags'] = ['fast']
        g = BuildStatusGenerator(tags=["fast"])
        self.assertTrue(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_schedulers_sends_mail(self):
        build = yield self.insert_build_finished_get_props(SUCCESS)
        g = BuildStatusGenerator(schedulers=['checkin'])
        self.assertTrue(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_schedulers_doesnt_send_mail(self):
        build = yield self.insert_build_finished_get_props(SUCCESS)
        g = BuildStatusGenerator(schedulers=['some-random-scheduler'])
        self.assertFalse(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_branches_sends_mail(self):
        build = yield self.insert_build_finished_get_props(SUCCESS)
        g = BuildStatusGenerator(branches=['refs/pull/34/merge'])
        self.assertTrue(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_branches_doesnt_send_mail(self):
        build = yield self.insert_build_finished_get_props(SUCCESS)
        g = BuildStatusGenerator(branches=['some-random-branch'])
        self.assertFalse(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def run_simple_test_sends_message_for_mode(self, mode, result, should_send=True):
        build = yield self.insert_build_finished_get_props(result)

        g = BuildStatusGenerator(mode=mode)

        self.assertEqual(g.is_message_needed_by_results(build), should_send)

    def run_simple_test_ignores_message_for_mode(self, mode, result):
        return self.run_simple_test_sends_message_for_mode(mode, result, False)

    def test_is_message_needed_mode_all_for_success(self):
        return self.run_simple_test_sends_message_for_mode("all", SUCCESS)

    def test_is_message_needed_mode_all_for_failure(self):
        return self.run_simple_test_sends_message_for_mode("all", FAILURE)

    def test_is_message_needed_mode_all_for_warnings(self):
        return self.run_simple_test_sends_message_for_mode("all", WARNINGS)

    def test_is_message_needed_mode_all_for_exception(self):
        return self.run_simple_test_sends_message_for_mode("all", EXCEPTION)

    def test_is_message_needed_mode_all_for_cancelled(self):
        return self.run_simple_test_sends_message_for_mode("all", CANCELLED)

    def test_is_message_needed_mode_failing_for_success(self):
        return self.run_simple_test_ignores_message_for_mode("failing", SUCCESS)

    def test_is_message_needed_mode_failing_for_failure(self):
        return self.run_simple_test_sends_message_for_mode("failing", FAILURE)

    def test_is_message_needed_mode_failing_for_warnings(self):
        return self.run_simple_test_ignores_message_for_mode("failing", WARNINGS)

    def test_is_message_needed_mode_failing_for_exception(self):
        return self.run_simple_test_ignores_message_for_mode("failing", EXCEPTION)

    def test_is_message_needed_mode_exception_for_success(self):
        return self.run_simple_test_ignores_message_for_mode("exception", SUCCESS)

    def test_is_message_needed_mode_exception_for_failure(self):
        return self.run_simple_test_ignores_message_for_mode("exception", FAILURE)

    def test_is_message_needed_mode_exception_for_warnings(self):
        return self.run_simple_test_ignores_message_for_mode("exception", WARNINGS)

    def test_is_message_needed_mode_exception_for_exception(self):
        return self.run_simple_test_sends_message_for_mode("exception", EXCEPTION)

    def test_is_message_needed_mode_warnings_for_success(self):
        return self.run_simple_test_ignores_message_for_mode("warnings", SUCCESS)

    def test_is_message_needed_mode_warnings_for_failure(self):
        return self.run_simple_test_sends_message_for_mode("warnings", FAILURE)

    def test_is_message_needed_mode_warnings_for_warnings(self):
        return self.run_simple_test_sends_message_for_mode("warnings", WARNINGS)

    def test_is_message_needed_mode_warnings_for_exception(self):
        return self.run_simple_test_ignores_message_for_mode("warnings", EXCEPTION)

    def test_is_message_needed_mode_passing_for_success(self):
        return self.run_simple_test_sends_message_for_mode("passing", SUCCESS)

    def test_is_message_needed_mode_passing_for_failure(self):
        return self.run_simple_test_ignores_message_for_mode("passing", FAILURE)

    def test_is_message_needed_mode_passing_for_warnings(self):
        return self.run_simple_test_ignores_message_for_mode("passing", WARNINGS)

    def test_is_message_needed_mode_passing_for_exception(self):
        return self.run_simple_test_ignores_message_for_mode("passing", EXCEPTION)

    @defer.inlineCallbacks
    def run_sends_message_for_problems(self, mode, results1, results2, should_send=True):
        build = yield self.insert_build_finished_get_props(results2)

        g = BuildStatusGenerator(mode=mode)

        if results1 is not None:
            build['prev_build'] = copy.deepcopy(build)
            build['prev_build']['results'] = results1
        else:
            build['prev_build'] = None
        self.assertEqual(g.is_message_needed_by_results(build), should_send)

    def test_is_message_needed_mode_problem_sends_on_problem(self):
        return self.run_sends_message_for_problems("problem", SUCCESS, FAILURE, True)

    def test_is_message_needed_mode_problem_ignores_successful_build(self):
        return self.run_sends_message_for_problems("problem", SUCCESS, SUCCESS, False)

    def test_is_message_needed_mode_problem_ignores_two_failed_builds_in_sequence(self):
        return self.run_sends_message_for_problems("problem", FAILURE, FAILURE, False)

    def test_is_message_needed_mode_change_sends_on_change(self):
        return self.run_sends_message_for_problems("change", FAILURE, SUCCESS, True)

    def test_is_message_needed_mode_change_sends_on_failure(self):
        return self.run_sends_message_for_problems("change", SUCCESS, FAILURE, True)

    def test_is_message_needed_mode_change_ignores_first_build(self):
        return self.run_sends_message_for_problems("change", None, FAILURE, False)

    def test_is_message_needed_mode_change_ignores_first_build2(self):
        return self.run_sends_message_for_problems("change", None, SUCCESS, False)

    def test_is_message_needed_mode_change_ignores_same_result_in_sequence(self):
        return self.run_sends_message_for_problems("change", SUCCESS, SUCCESS, False)

    def test_is_message_needed_mode_change_ignores_same_result_in_sequence2(self):
        return self.run_sends_message_for_problems("change", FAILURE, FAILURE, False)

    @defer.inlineCallbacks
    def setup_generator(self, results=SUCCESS, message=None, db_args=None, **kwargs):
        if message is None:
            message = {
                "body": "body",
                "type": "text",
                "subject": "subject"
            }
        if db_args is None:
            db_args = {}

        build = yield self.insert_build_finished_get_props(results, **db_args)

        g = BuildStatusGenerator(**kwargs)

        g.formatter = Mock(spec=g.formatter)
        g.formatter.format_message_for_build.return_value = message

        return (g, build)

    @defer.inlineCallbacks
    def build_message(self, g, builds, results=SUCCESS):
        reporter = Mock()
        reporter.getResponsibleUsersForBuild.return_value = []

        report = yield g.build_message(g.formatter, self.master, reporter, "mybldr", builds,
                                       results)
        return report

    @defer.inlineCallbacks
    def generate(self, g, key, build):
        reporter = Mock()
        reporter.getResponsibleUsersForBuild.return_value = []

        report = yield g.generate(self.master, reporter, key, build)
        return report

    @defer.inlineCallbacks
    def test_build_message_nominal(self):
        g, build = yield self.setup_generator(mode=("change",))
        report = yield self.build_message(g, [build])

        g.formatter.format_message_for_build.assert_called_with(('change',), 'mybldr', build,
                                                                self.master, [])

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
            'builder_name': 'mybldr',
            'results': SUCCESS,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_build_message_no_result(self):
        g, build = yield self.setup_generator(results=None, mode=("change",))
        report = yield self.build_message(g, [build], results=None)

        g.formatter.format_message_for_build.assert_called_with(('change',), 'mybldr', build,
                                                                self.master, [])

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
            'builder_name': 'mybldr',
            'results': None,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_build_message_no_result_default_subject(self):
        subject = 'result: %(result)s builder: %(builder)s title: %(title)s'
        message = {
            "body": "body",
            "type": "text",
            "subject": None,
        }

        g, build = yield self.setup_generator(results=None, subject=subject,
                                              message=message, mode=("change",))
        report = yield self.build_message(g, [build], results=None)

        g.formatter.format_message_for_build.assert_called_with(('change',), 'mybldr', build,
                                                                self.master, [])

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'result: not finished builder: mybldr title: Buildbot',
            'type': 'text',
            'builder_name': 'mybldr',
            'results': None,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_build_message_addLogs(self):
        g, build = yield self.setup_generator(mode=("change",), add_logs=True)
        report = yield self.build_message(g, [build])

        self.assertEqual(report['logs'][0]['logid'], 60)
        self.assertIn("log with", report['logs'][0]['content']['content'])

    @defer.inlineCallbacks
    def test_build_message_add_patch(self):
        g, build = yield self.setup_generator(mode=("change",), add_patch=True,
                                              db_args={'insert_patch': True})
        report = yield self.build_message(g, [build])

        patch_dict = {
            'author': 'him@foo',
            'body': b'hello, world',
            'comment': 'foo',
            'level': 3,
            'patchid': 99,
            'subdir': '/foo'
        }
        self.assertEqual(report['patches'], [patch_dict])

    @defer.inlineCallbacks
    def test_build_message_add_patch_no_patch(self):
        g, build = yield self.setup_generator(mode=("change",), add_patch=True,
                                              db_args={'insert_patch': False})
        report = yield self.build_message(g, [build])
        self.assertEqual(report['patches'], [])

    @defer.inlineCallbacks
    def test_generate_finished(self):
        g, build = yield self.setup_generator()
        report = yield self.generate(g, ('builds', 123, 'finished'), build)

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
            'builder_name': 'Builder0',
            'results': SUCCESS,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_generate_new(self):
        g, build = yield self.setup_generator(results=None, mode=('failing',), report_new=True)
        report = yield self.generate(g, ('builds', 123, 'new'), build)

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
            'builder_name': 'Builder0',
            'results': None,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })


class TestBuildStartEndGenerator(ConfigErrorsMixin, TestReactorMixin,
                                 unittest.TestCase, ReporterTestMixin):

    all_messages = ('failing', 'passing', 'warnings', 'exception', 'cancelled')

    def setUp(self):
        self.setUpTestReactor()
        self.setup_reporter_test()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

    @defer.inlineCallbacks
    def insert_build_finished_get_props(self, results, **kwargs):
        build = yield self.insert_build_finished(results, **kwargs)
        yield utils.getDetailsForBuild(self.master, build, wantProperties=True)
        return build

    @parameterized.expand([
        ('tags', 'tag'),
        ('tags', 1),
        ('builders', 'builder'),
        ('builders', 1),
        ('schedulers', 'scheduler'),
        ('schedulers', 1),
        ('branches', 'branch'),
        ('branches', 1),
    ])
    def test_list_params_check_raises(self, arg_name, arg_value):
        kwargs = {arg_name: arg_value}
        g = BuildStartEndStatusGenerator(**kwargs)
        with self.assertRaisesConfigError('must be a list or None'):
            g.check()

    def setup_generator(self, results=SUCCESS, start_message=None, end_message=None, **kwargs):
        if start_message is None:
            start_message = {
                "body": "start body",
                "type": "plain",
                "subject": "start subject"
            }

        if end_message is None:
            end_message = {
                "body": "end body",
                "type": "plain",
                "subject": "end subject"
            }

        g = BuildStartEndStatusGenerator(**kwargs)

        g.start_formatter = Mock(spec=g.start_formatter)
        g.start_formatter.format_message_for_build.return_value = start_message
        g.end_formatter = Mock(spec=g.end_formatter)
        g.end_formatter.format_message_for_build.return_value = end_message

        return g

    @defer.inlineCallbacks
    def build_message(self, g, builds, results=SUCCESS):
        reporter = Mock()
        reporter.getResponsibleUsersForBuild.return_value = []

        report = yield g.build_message(g.start_formatter, self.master, reporter, "mybldr",
                                       builds, results)
        return report

    @defer.inlineCallbacks
    def generate(self, g, key, build):
        reporter = Mock()
        reporter.getResponsibleUsersForBuild.return_value = []

        report = yield g.generate(self.master, reporter, key, build)
        return report

    @defer.inlineCallbacks
    def test_build_message_start(self):
        g = yield self.setup_generator()
        build = yield self.insert_build_finished_get_props(SUCCESS)
        report = yield self.build_message(g, [build])

        g.start_formatter.format_message_for_build.assert_called_with(
            self.all_messages, 'mybldr', build, self.master, [])

        self.assertEqual(report, {
            'body': 'start body',
            'subject': 'start subject',
            'type': 'plain',
            'builder_name': 'mybldr',
            'results': SUCCESS,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_build_message_start_no_result(self):
        g = yield self.setup_generator(results=None)
        build = yield self.insert_build_new()
        report = yield self.build_message(g, [build], results=None)

        g.start_formatter.format_message_for_build.assert_called_with(
            self.all_messages, 'mybldr', build, self.master, [])

        self.assertEqual(report, {
            'body': 'start body',
            'subject': 'start subject',
            'type': 'plain',
            'builder_name': 'mybldr',
            'results': None,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_build_message_add_logs(self):
        g = yield self.setup_generator(add_logs=True)
        build = yield self.insert_build_finished_get_props(SUCCESS)
        report = yield self.build_message(g, [build])

        self.assertEqual(report['logs'][0]['logid'], 60)
        self.assertIn("log with", report['logs'][0]['content']['content'])

    @defer.inlineCallbacks
    def test_build_message_add_patch(self):
        g = yield self.setup_generator(add_patch=True)
        build = yield self.insert_build_finished_get_props(SUCCESS, insert_patch=True)
        report = yield self.build_message(g, [build])

        patch_dict = {
            'author': 'him@foo',
            'body': b'hello, world',
            'comment': 'foo',
            'level': 3,
            'patchid': 99,
            'subdir': '/foo'
        }
        self.assertEqual(report['patches'], [patch_dict])

    @defer.inlineCallbacks
    def test_build_message_add_patch_no_patch(self):
        g = yield self.setup_generator(add_patch=True)
        build = yield self.insert_build_finished_get_props(SUCCESS, insert_patch=False)
        report = yield self.build_message(g, [build])
        self.assertEqual(report['patches'], [])

    @defer.inlineCallbacks
    def test_generate_new(self):
        g = yield self.setup_generator()
        build = yield self.insert_build_new()
        report = yield self.generate(g, ('builds', 123, 'new'), build)

        self.assertEqual(report, {
            'body': 'start body',
            'subject': 'start subject',
            'type': 'plain',
            'builder_name': 'Builder0',
            'results': None,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_generate_finished(self):
        g = yield self.setup_generator()
        build = yield self.insert_build_finished_get_props(SUCCESS)
        report = yield self.generate(g, ('builds', 123, 'finished'), build)

        self.assertEqual(report, {
            'body': 'end body',
            'subject': 'end subject',
            'type': 'plain',
            'builder_name': 'Builder0',
            'results': SUCCESS,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_generate_none(self):
        g = yield self.setup_generator(builders=['other builder'])
        build = yield self.insert_build_new()
        report = yield self.generate(g, ('builds', 123, 'new'), build)

        self.assertIsNone(report, None)
