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


from parameterized import parameterized

from mock import Mock

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
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.warnings import DeprecatedApiWarning


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
        g, build = yield self.setup_generator(mode=("change",))
        report = yield self.build_message(g, build)

        g.formatter.format_message_for_build.assert_called_with(self.master, build,
                                                                is_buildset=False,
                                                                mode=('change',), users=[])

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
            'results': SUCCESS,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_build_message_no_result(self):
        g, build = yield self.setup_generator(results=None, mode=("change",))
        report = yield self.build_message(g, build, results=None)

        g.formatter.format_message_for_build.assert_called_with(self.master, build,
                                                                is_buildset=False,
                                                                mode=('change',), users=[])

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
            'results': None,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_build_subject_deprecated(self):
        with assertProducesWarning(DeprecatedApiWarning, "subject parameter"):
            yield self.setup_generator(subject='subject')

    @defer.inlineCallbacks
    def test_build_message_no_result_formatter_no_subject(self):
        message = {
            "body": "body",
            "type": "text",
            "subject": None,  # deprecated unspecified subject
        }

        g, build = yield self.setup_generator(results=None, message=message, mode=("change",))
        report = yield self.build_message(g, build, results=None)

        g.formatter.format_message_for_build.assert_called_with(self.master, build,
                                                                is_buildset=False,
                                                                mode=('change',), users=[])

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'Buildbot not finished in Buildbot on Builder0',
            'type': 'text',
            'results': None,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_build_message_addLogs(self):
        g, build = yield self.setup_generator(mode=("change",), add_logs=True)
        report = yield self.build_message(g, build)

        self.assertEqual(report['logs'][0]['logid'], 60)
        self.assertIn("log with", report['logs'][0]['content']['content'])

    @defer.inlineCallbacks
    def test_build_message_add_patch(self):
        g, build = yield self.setup_generator(mode=("change",), add_patch=True,
                                              db_args={'insert_patch': True})
        report = yield self.build_message(g, build)

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
        report = yield self.build_message(g, build)
        self.assertEqual(report['patches'], [])

    @defer.inlineCallbacks
    def test_generate_finished(self):
        g, build = yield self.setup_generator()
        report = yield self.generate(g, ('builds', 123, 'finished'), build)

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
            'results': SUCCESS,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_generate_finished_non_matching_builder(self):
        g, build = yield self.setup_generator(builders=['non-matched'])
        report = yield self.generate(g, ('builds', 123, 'finished'), build)

        self.assertIsNone(report)

    @defer.inlineCallbacks
    def test_generate_finished_non_matching_result(self):
        g, build = yield self.setup_generator(mode=('failing',))
        report = yield self.generate(g, ('builds', 123, 'finished'), build)

        self.assertIsNone(report)

    @defer.inlineCallbacks
    def test_generate_new(self):
        g, build = yield self.setup_generator(results=None, mode=('failing',), report_new=True)
        report = yield self.generate(g, ('builds', 123, 'new'), build)

        self.assertEqual(report, {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
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
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

    @defer.inlineCallbacks
    def insert_build_finished_get_props(self, results, **kwargs):
        build = yield self.insert_build_finished(results, **kwargs)
        yield utils.getDetailsForBuild(self.master, build, want_properties=True)
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
        report = yield self.build_message(g, build)

        g.start_formatter.format_message_for_build.assert_called_with(self.master, build,
                                                                      is_buildset=False,
                                                                      mode=self.all_messages,
                                                                      users=[])

        self.assertEqual(report, {
            'body': 'start body',
            'subject': 'start subject',
            'type': 'plain',
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
        report = yield self.build_message(g, build, results=None)

        g.start_formatter.format_message_for_build.assert_called_with(self.master, build,
                                                                      is_buildset=False,
                                                                      mode=self.all_messages,
                                                                      users=[])

        self.assertEqual(report, {
            'body': 'start body',
            'subject': 'start subject',
            'type': 'plain',
            'results': None,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })

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
        g = yield self.setup_generator(add_logs=True)
        build = yield self.insert_build_finished_get_props(SUCCESS)
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
            'subdir': '/foo'
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
        report = yield self.generate(g, ('builds', 123, 'new'), build)

        self.assertEqual(report, {
            'body': 'start body',
            'subject': 'start subject',
            'type': 'plain',
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
