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


from unittest.mock import Mock

from parameterized import parameterized
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import SUCCESS
from buildbot.reporters import utils
from buildbot.reporters.generators.build import BuildStartEndStatusGenerator
from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.reporter import ReporterTestMixin
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.warnings import DeprecatedApiWarning


class TestBuildGenerator(ConfigErrorsMixin, TestReactorMixin, unittest.TestCase, ReporterTestMixin):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.master = yield fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)

    @defer.inlineCallbacks
    def insert_build_finished_get_props(
        self, results, add_logs=None, want_logs_content=False, **kwargs
    ):
        build = yield self.insert_build_finished(results, **kwargs)
        yield utils.getDetailsForBuild(
            self.master,
            build,
            want_properties=True,
            add_logs=add_logs,
            want_logs_content=want_logs_content,
        )
        return build

    @defer.inlineCallbacks
    def setup_generator(
        self,
        results=SUCCESS,
        message=None,
        db_args=None,
        add_logs=None,
        want_logs_content=False,
        **kwargs,
    ):
        if message is None:
            message = {
                "body": "body",
                "type": "text",
                "subject": "subject",
                "extra_info": None,
            }
        if db_args is None:
            db_args = {}

        build = yield self.insert_build_finished_get_props(
            results, want_logs_content=want_logs_content, add_logs=add_logs, **db_args
        )
        buildset = yield self.get_inserted_buildset()

        g = BuildStatusGenerator(add_logs=add_logs, **kwargs)

        g.formatter = Mock(spec=g.formatter)
        g.formatter.want_logs_content = want_logs_content
        g.formatter.format_message_for_build.return_value = message

        return g, build, buildset

    @defer.inlineCallbacks
    def build_message(self, g, build, results=SUCCESS):
        reporter = Mock()
        reporter.getResponsibleUsersForBuild.return_value = []

        report = yield g.build_message(g.formatter, self.master, reporter, build)
        return report

    @defer.inlineCallbacks
    def generate(self, g, key, build):
        reporter = Mock()
        reporter.getResponsibleUsersForBuild.return_value = []

        report = yield g.generate(self.master, reporter, key, build)
        return report

    @defer.inlineCallbacks
    def test_build_message_nominal(self):
        g, build, buildset = yield self.setup_generator(mode=("change",))
        report = yield self.build_message(g, build)

        g.formatter.format_message_for_build.assert_called_with(
            self.master, build, is_buildset=False, mode=('change',), users=[]
        )

        self.assertEqual(
            report,
            {
                'body': 'body',
                'subject': 'subject',
                'type': 'text',
                "extra_info": None,
                'results': SUCCESS,
                'builds': [build],
                "buildset": buildset,
                'users': [],
                'patches': [],
                'logs': [],
            },
        )

    @defer.inlineCallbacks
    def test_build_message_no_result(self):
        g, build, buildset = yield self.setup_generator(results=None, mode=("change",))
        report = yield self.build_message(g, build, results=None)

        g.formatter.format_message_for_build.assert_called_with(
            self.master, build, is_buildset=False, mode=('change',), users=[]
        )

        self.assertEqual(
            report,
            {
                'body': 'body',
                'subject': 'subject',
                'type': 'text',
                "extra_info": None,
                'results': None,
                'builds': [build],
                "buildset": buildset,
                'users': [],
                'patches': [],
                'logs': [],
            },
        )

    @defer.inlineCallbacks
    def test_build_message_no_result_formatter_no_subject(self):
        message = {
            "body": "body",
            "type": "text",
            "subject": None,  # deprecated unspecified subject
            "extra_info": None,
        }

        g, build, buildset = yield self.setup_generator(
            results=None, message=message, mode=("change",)
        )
        report = yield self.build_message(g, build, results=None)

        g.formatter.format_message_for_build.assert_called_with(
            self.master, build, is_buildset=False, mode=('change',), users=[]
        )

        self.assertEqual(
            report,
            {
                'body': 'body',
                'subject': 'Buildbot not finished in Buildbot on Builder0',
                'type': 'text',
                "extra_info": None,
                'results': None,
                'builds': [build],
                "buildset": buildset,
                'users': [],
                'patches': [],
                'logs': [],
            },
        )

    @defer.inlineCallbacks
    def test_build_message_addLogs(self):
        with assertProducesWarnings(
            DeprecatedApiWarning,
            message_pattern=".*argument add_logs have been deprecated.*",
        ):
            g, build, _ = yield self.setup_generator(mode=("change",), add_logs=True)
        report = yield self.build_message(g, build)

        self.assertEqual(report['logs'][0]['logid'], 60)
        self.assertIn("log with", report['logs'][0]['content']['content'])

    @defer.inlineCallbacks
    def test_build_message_want_logs_content(self):
        g, build, _ = yield self.setup_generator(mode=("change",), want_logs_content=True)
        report = yield self.build_message(g, build)

        self.assertEqual(report['logs'][0]['logid'], 60)
        self.assertIn("log with", report['logs'][0]['content']['content'])

    @defer.inlineCallbacks
    def test_build_message_add_patch(self):
        g, build, _ = yield self.setup_generator(
            mode=("change",), add_patch=True, db_args={"insert_patch": True}
        )
        report = yield self.build_message(g, build)

        patch_dict = {
            'author': 'him@foo',
            'body': b'hello, world',
            'comment': 'foo',
            'level': 3,
            'patchid': 99,
            'subdir': '/foo',
        }
        self.assertEqual(report['patches'], [patch_dict])

    @defer.inlineCallbacks
    def test_build_message_add_patch_no_patch(self):
        g, build, _ = yield self.setup_generator(
            mode=("change",), add_patch=True, db_args={'insert_patch': False}
        )
        report = yield self.build_message(g, build)
        self.assertEqual(report['patches'], [])

    @defer.inlineCallbacks
    def test_generate_finished(self):
        g, build, buildset = yield self.setup_generator()
        report = yield self.generate(g, ('builds', 123, 'finished'), build)

        self.assertEqual(
            report,
            {
                'body': 'body',
                'subject': 'subject',
                'type': 'text',
                "extra_info": None,
                'results': SUCCESS,
                'builds': [build],
                "buildset": buildset,
                'users': [],
                'patches': [],
                'logs': [],
            },
        )

    @defer.inlineCallbacks
    def test_generate_finished_non_matching_builder(self):
        g, build, _ = yield self.setup_generator(builders=['non-matched'])
        report = yield self.generate(g, ('builds', 123, 'finished'), build)

        self.assertIsNone(report)

    @defer.inlineCallbacks
    def test_generate_finished_non_matching_result(self):
        g, build, _ = yield self.setup_generator(mode=('failing',))
        report = yield self.generate(g, ('builds', 123, 'finished'), build)

        self.assertIsNone(report)

    @defer.inlineCallbacks
    def test_generate_new(self):
        g, build, buildset = yield self.setup_generator(
            results=None, mode=("failing",), report_new=True
        )
        report = yield self.generate(g, ('builds', 123, 'new'), build)

        self.assertEqual(
            report,
            {
                'body': 'body',
                'subject': 'subject',
                'type': 'text',
                "extra_info": None,
                'results': None,
                'builds': [build],
                "buildset": buildset,
                'users': [],
                'patches': [],
                'logs': [],
            },
        )


class TestBuildStartEndGenerator(
    ConfigErrorsMixin, TestReactorMixin, unittest.TestCase, ReporterTestMixin
):
    all_messages = ('failing', 'passing', 'warnings', 'exception', 'cancelled')

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.master = yield fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)

    @defer.inlineCallbacks
    def insert_build_finished_get_props(
        self, results, add_logs=None, want_logs_content=False, **kwargs
    ):
        build = yield self.insert_build_finished(results, **kwargs)
        yield utils.getDetailsForBuild(
            self.master,
            build,
            want_properties=True,
            add_logs=add_logs,
            want_logs_content=want_logs_content,
        )
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

    def setup_generator(
        self,
        results=SUCCESS,
        start_message=None,
        end_message=None,
        want_logs_content=False,
        **kwargs,
    ):
        if start_message is None:
            start_message = {
                "body": "start body",
                "type": "plain",
                "subject": "start subject",
                "extra_info": None,
            }

        if end_message is None:
            end_message = {
                "body": "end body",
                "type": "plain",
                "subject": "end subject",
                "extra_info": None,
            }

        g = BuildStartEndStatusGenerator(**kwargs)

        g.start_formatter = Mock(spec=g.start_formatter)
        g.start_formatter.want_logs_content = want_logs_content
        g.start_formatter.format_message_for_build.return_value = start_message
        g.end_formatter = Mock(spec=g.end_formatter)
        g.end_formatter.want_logs_content = want_logs_content
        g.end_formatter.format_message_for_build.return_value = end_message

        return g

    @defer.inlineCallbacks
    def build_message(self, g, build, results=SUCCESS):
        reporter = Mock()
        reporter.getResponsibleUsersForBuild.return_value = []

        report = yield g.build_message(g.start_formatter, self.master, reporter, build)
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
        buildset = yield self.get_inserted_buildset()
        report = yield self.build_message(g, build)

        g.start_formatter.format_message_for_build.assert_called_with(
            self.master, build, is_buildset=False, mode=self.all_messages, users=[]
        )

        self.assertEqual(
            report,
            {
                'body': 'start body',
                'subject': 'start subject',
                'type': 'plain',
                "extra_info": None,
                'results': SUCCESS,
                'builds': [build],
                "buildset": buildset,
                'users': [],
                'patches': [],
                'logs': [],
            },
        )

    @defer.inlineCallbacks
    def test_build_message_start_no_result(self):
        g = yield self.setup_generator(results=None)
        build = yield self.insert_build_new()
        buildset = yield self.get_inserted_buildset()
        build["buildset"] = buildset
        report = yield self.build_message(g, build, results=None)

        g.start_formatter.format_message_for_build.assert_called_with(
            self.master, build, is_buildset=False, mode=self.all_messages, users=[]
        )

        self.assertEqual(
            report,
            {
                'body': 'start body',
                'subject': 'start subject',
                'type': 'plain',
                "extra_info": None,
                'results': None,
                'builds': [build],
                "buildset": buildset,
                'users': [],
                'patches': [],
                'logs': [],
            },
        )

    @defer.inlineCallbacks
    def test_is_message_needed_ignores_unspecified_tags(self):
        build = yield self.insert_build_finished_get_props(SUCCESS)

        # force tags
        build['builder']['tags'] = ['tag']
        g = BuildStartEndStatusGenerator(tags=['not_existing_tag'])
        self.assertFalse(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_is_message_needed_tags(self):
        build = yield self.insert_build_finished_get_props(SUCCESS)

        # force tags
        build['builder']['tags'] = ['tag']
        g = BuildStartEndStatusGenerator(tags=['tag'])
        self.assertTrue(g.is_message_needed_by_props(build))

    @defer.inlineCallbacks
    def test_build_message_add_logs(self):
        with assertProducesWarnings(
            DeprecatedApiWarning,
            message_pattern=".*argument add_logs have been deprecated.*",
        ):
            g = yield self.setup_generator(add_logs=True)
        build = yield self.insert_build_finished_get_props(SUCCESS, add_logs=True)
        report = yield self.build_message(g, build)

        self.assertEqual(report['logs'][0]['logid'], 60)
        self.assertIn("log with", report['logs'][0]['content']['content'])

    @defer.inlineCallbacks
    def test_build_message_want_logs_content(self):
        g = yield self.setup_generator(want_logs_content=True)
        build = yield self.insert_build_finished_get_props(SUCCESS, want_logs_content=True)
        report = yield self.build_message(g, build)

        self.assertEqual(report['logs'][0]['logid'], 60)
        self.assertIn("log with", report['logs'][0]['content']['content'])

    @defer.inlineCallbacks
    def test_build_message_add_patch(self):
        g = yield self.setup_generator(add_patch=True)
        build = yield self.insert_build_finished_get_props(SUCCESS, insert_patch=True)
        report = yield self.build_message(g, build)

        patch_dict = {
            'author': 'him@foo',
            'body': b'hello, world',
            'comment': 'foo',
            'level': 3,
            'patchid': 99,
            'subdir': '/foo',
        }
        self.assertEqual(report['patches'], [patch_dict])

    @defer.inlineCallbacks
    def test_build_message_add_patch_no_patch(self):
        g = yield self.setup_generator(add_patch=True)
        build = yield self.insert_build_finished_get_props(SUCCESS, insert_patch=False)
        report = yield self.build_message(g, build)
        self.assertEqual(report['patches'], [])

    @defer.inlineCallbacks
    def test_generate_new(self):
        g = yield self.setup_generator()
        build = yield self.insert_build_new()
        buildset = yield self.get_inserted_buildset()
        report = yield self.generate(g, ('builds', 123, 'new'), build)

        self.assertEqual(
            report,
            {
                'body': 'start body',
                'subject': 'start subject',
                'type': 'plain',
                "extra_info": None,
                'results': None,
                'builds': [build],
                "buildset": buildset,
                'users': [],
                'patches': [],
                'logs': [],
            },
        )

    @defer.inlineCallbacks
    def test_generate_finished(self):
        g = yield self.setup_generator()
        build = yield self.insert_build_finished_get_props(SUCCESS)
        buildset = yield self.get_inserted_buildset()
        report = yield self.generate(g, ('builds', 123, 'finished'), build)

        self.assertEqual(
            report,
            {
                'body': 'end body',
                'subject': 'end subject',
                'type': 'plain',
                "extra_info": None,
                'results': SUCCESS,
                'builds': [build],
                "buildset": buildset,
                'users': [],
                'patches': [],
                'logs': [],
            },
        )

    @defer.inlineCallbacks
    def test_generate_none(self):
        g = yield self.setup_generator(builders=['other builder'])
        build = yield self.insert_build_new()
        build["buildset"] = yield self.get_inserted_buildset()
        report = yield self.generate(g, ('builds', 123, 'new'), build)

        self.assertIsNone(report, None)
