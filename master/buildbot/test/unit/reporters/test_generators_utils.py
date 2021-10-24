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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import CANCELLED
from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.reporters import utils
from buildbot.reporters.generators.utils import BuildStatusGeneratorMixin
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.reporter import ReporterTestMixin


class TestBuildGenerator(ConfigErrorsMixin, TestReactorMixin,
                         unittest.TestCase, ReporterTestMixin):

    def setUp(self):
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

    @defer.inlineCallbacks
    def insert_build_finished_get_props(self, results, **kwargs):
        build = yield self.insert_build_finished(results, **kwargs)
        yield utils.getDetailsForBuild(self.master, build, want_properties=True)
        return build

    def create_generator(self, mode=("failing", "passing", "warnings"),
                         tags=None, builders=None, schedulers=None, branches=None,
                         subject="Some subject", add_logs=False, add_patch=False):
        return BuildStatusGeneratorMixin(mode, tags, builders, schedulers, branches, subject,
                                         add_logs, add_patch)

    def test_generate_name(self):
        g = self.create_generator(tags=['tag1', 'tag2'], builders=['b1', 'b2'],
                                  schedulers=['s1', 's2'], branches=['b1', 'b2'])
        self.assertEqual(g.generate_name(),
                         'BuildStatusGeneratorMixin_tags_tag1+tag2_builders_b1+b2_' +
                         'schedulers_s1+s2_branches_b1+b2failing_passing_warnings')

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
        g = self.create_generator(**kwargs)
        with self.assertRaisesConfigError('must be a list or None'):
            g.check()

    @parameterized.expand([
        ('unknown_str', 'unknown', 'not a valid mode'),
        ('unknown_list', ['unknown'], 'not a valid mode'),
        ('unknown_list_two', ['unknown', 'failing'], 'not a valid mode'),
        ('all_in_list', ['all', 'failing'], 'must be passed in as a separate string'),
    ])
    def test_tag_check_raises(self, name, mode, expected_exception):
        g = self.create_generator(mode=mode)
        with self.assertRaisesConfigError(expected_exception):
            g.check()

    def test_subject_newlines_not_allowed(self):
        g = self.create_generator(subject='subject\nwith\nnewline')
        with self.assertRaisesConfigError('Newlines are not allowed'):
            g.check()

    @defer.inlineCallbacks
    def test_is_message_needed_ignores_unspecified_tags(self):
        build = yield self.insert_build_finished_get_props(SUCCESS)

        # force tags
        build['builder']['tags'] = ['slow']
        g = self.create_generator(tags=["fast"])
        self.assertFalse(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_tags(self):
        build = yield self.insert_build_finished_get_props(SUCCESS)

        # force tags
        build['builder']['tags'] = ['fast']
        g = self.create_generator(tags=["fast"])
        self.assertTrue(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_schedulers_sends_mail(self):
        build = yield self.insert_build_finished_get_props(SUCCESS)
        g = self.create_generator(schedulers=['checkin'])
        self.assertTrue(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_schedulers_doesnt_send_mail(self):
        build = yield self.insert_build_finished_get_props(SUCCESS)
        g = self.create_generator(schedulers=['some-random-scheduler'])
        self.assertFalse(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_branches_sends_mail(self):
        build = yield self.insert_build_finished_get_props(SUCCESS)
        g = self.create_generator(branches=['refs/pull/34/merge'])
        self.assertTrue(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_branches_doesnt_send_mail(self):
        build = yield self.insert_build_finished_get_props(SUCCESS)
        g = self.create_generator(branches=['some-random-branch'])
        self.assertFalse(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def run_simple_test_sends_message_for_mode(self, mode, result, should_send=True):
        build = yield self.insert_build_finished_get_props(result)

        g = self.create_generator(mode=mode)

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

        g = self.create_generator(mode=mode)

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

    @parameterized.expand([
        ('bool_true', True, 'step', 'log', True),
        ('bool_false', False, 'step', 'log', False),
        ('match_by_log_name', ['log'], 'step', 'log', True),
        ('no_match_by_log_name', ['not_existing'], 'step', 'log', False),
        ('match_by_log_step_name', ['step.log'], 'step', 'log', True),
        ('no_match_by_log_step_name', ['step1.log1'], 'step', 'log', False),
    ])
    def test_should_attach_log(self, name, add_logs, log_step_name, log_name, expected_result):
        g = self.create_generator(add_logs=add_logs)
        log = {'stepname': log_step_name, 'name': log_name}
        self.assertEqual(g._should_attach_log(log), expected_result)

    @parameterized.expand([
        ('both_none', None, None, (None, False)),
        ('old_none', None, 'type', ('type', True)),
        ('new_none', 'type', None, ('type', False)),
        ('same', 'type', 'type', ('type', True)),
        ('different', 'type1', 'type2', ('type1', False)),
    ])
    def test_merge_msgtype(self, name, old, new, expected_result):
        g = self.create_generator()
        self.assertEqual(g._merge_msgtype(old, new), expected_result)

    @parameterized.expand([
        ('both_none', None, None, None),
        ('old_none', None, 'sub', 'sub'),
        ('new_none', 'sub', None, 'sub'),
        ('same', 'sub', 'sub', 'sub'),
        ('different', 'sub1', 'sub2', 'sub1'),
    ])
    def test_merge_subject(self, name, old, new, expected_result):
        g = self.create_generator()
        self.assertEqual(g._merge_subject(old, new), expected_result)

    @parameterized.expand([
        ('both_none', None, None, (None, True)),
        ('old_none', None, 'body', ('body', True)),
        ('new_none', 'body', None, ('body', True)),
        ('both_str', 'body1\n', 'body2\n', ('body1\nbody2\n', True)),
        ('both_list', ['body1'], ['body2'], (['body1', 'body2'], True)),
        ('both_dict', {'v': 'body1'}, {'v': 'body2'}, ({'v': 'body1'}, False)),
        ('str_list', ['body1'], 'body2', (['body1'], False)),
    ])
    def test_merge_body(self, name, old, new, expected_result):
        g = self.create_generator()
        self.assertEqual(g._merge_body(old, new), expected_result)
