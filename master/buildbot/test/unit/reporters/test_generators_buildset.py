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

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import SUCCESS
from buildbot.reporters import utils
from buildbot.reporters.generators.buildset import BuildSetCombinedStatusGenerator
from buildbot.reporters.generators.buildset import BuildSetStatusGenerator
from buildbot.reporters.message import MessageFormatter
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.reporter import ReporterTestMixin


class TestBuildSetGeneratorBase(
    ConfigErrorsMixin, TestReactorMixin, ReporterTestMixin, unittest.TestCase
):
    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.master = yield fakemaster.make_master(self, wantData=True, wantDb=True, wantMq=True)

    @defer.inlineCallbacks
    def insert_build_finished_get_props(self, results, **kwargs):
        build = yield self.insert_build_finished(results, **kwargs)
        yield utils.getDetailsForBuild(self.master, build, want_properties=True)
        return build

    @defer.inlineCallbacks
    def setup_generator(
        self, results=SUCCESS, message=None, db_args=None, insert_build=True, **kwargs
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

        if insert_build:
            build = yield self.insert_build_finished_get_props(results, **db_args)
            buildset = yield self.get_inserted_buildset()
        else:
            build = None
            buildset = yield self.insert_buildset_no_builds(results, **db_args)

        formatter = Mock(spec=MessageFormatter())
        formatter.format_message_for_build.return_value = message
        formatter.format_message_for_buildset.return_value = message
        formatter.want_logs = False
        formatter.want_logs_content = False
        formatter.want_steps = False

        g = self.GENERATOR_CLASS(message_formatter=formatter, **kwargs)

        return (g, build, buildset)


class TestBuildSetGenerator(TestBuildSetGeneratorBase):
    # Note: most of the functionality of BuildSetStatusGenerator is shared with
    # BuildStatusGenerator and is tested there.

    GENERATOR_CLASS = BuildSetStatusGenerator

    @defer.inlineCallbacks
    def buildset_message(self, g, builds, buildset):
        reporter = Mock()
        reporter.getResponsibleUsersForBuild.return_value = []

        report = yield g.buildset_message(g.formatter, self.master, reporter, builds, buildset)
        return report

    @defer.inlineCallbacks
    def generate(self, g, key, build):
        reporter = Mock()
        reporter.getResponsibleUsersForBuild.return_value = []

        report = yield g.generate(self.master, reporter, key, build)
        return report

    @defer.inlineCallbacks
    def test_buildset_message_nominal(self):
        g, build, buildset = yield self.setup_generator(mode=("change",))
        report = yield self.buildset_message(g, [build], buildset)

        g.formatter.format_message_for_build.assert_called_with(
            self.master, build, is_buildset=True, mode=('change',), users=[]
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
    def test_buildset_message_no_result(self):
        g, build, buildset = yield self.setup_generator(results=None, mode=("change",))
        buildset["results"] = None
        report = yield self.buildset_message(g, [build], buildset)

        g.formatter.format_message_for_build.assert_called_with(
            self.master, build, is_buildset=True, mode=('change',), users=[]
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
    def test_buildset_message_no_result_formatter_no_subject(self):
        message = {
            "body": "body",
            "type": "text",
            "subject": None,  # deprecated unspecified subject
            "extra_info": None,
        }

        g, build, buildset = yield self.setup_generator(
            results=None, message=message, mode=("change",)
        )
        buildset["results"] = None
        report = yield self.buildset_message(g, [build], buildset)

        g.formatter.format_message_for_build.assert_called_with(
            self.master, build, is_buildset=True, mode=('change',), users=[]
        )

        self.assertEqual(
            report,
            {
                'body': 'body',
                'subject': 'Buildbot not finished in Buildbot on whole buildset',
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
    def test_generate_complete(self):
        g, build, buildset = yield self.setup_generator()
        report = yield self.generate(g, ('buildsets', 98, 'complete'), buildset)

        # we retrieve build data differently when processing the buildset, so adjust it to match
        del build['buildrequest']
        del build['parentbuild']
        del build['parentbuilder']

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
    def test_generate_complete_no_builds(self):
        g, _, buildset = yield self.setup_generator(insert_build=False)
        report = yield self.generate(g, ('buildsets', 98, 'complete'), buildset)

        g.formatter.format_message_for_build.assert_not_called()
        self.assertIsNone(report)

    @defer.inlineCallbacks
    def test_generate_complete_non_matching_builder(self):
        g, _, buildset = yield self.setup_generator(builders=['non-matched'])
        report = yield self.generate(g, ('buildsets', 98, 'complete'), buildset)

        g.formatter.format_message_for_build.assert_not_called()
        self.assertIsNone(report)

    @defer.inlineCallbacks
    def test_generate_complete_non_matching_result(self):
        g, _, buildset = yield self.setup_generator(mode=('failing',))
        report = yield self.generate(g, ('buildsets', 98, 'complete'), buildset)

        g.formatter.format_message_for_build.assert_not_called()
        self.assertIsNone(report)


class TestBuildSetCombinedGenerator(TestBuildSetGeneratorBase):
    GENERATOR_CLASS = BuildSetCombinedStatusGenerator

    @defer.inlineCallbacks
    def buildset_message(self, g, buildset, builds):
        reporter = Mock()
        report = yield g.buildset_message(g.formatter, self.master, reporter, buildset, builds)
        return report

    @defer.inlineCallbacks
    def generate(self, g, key, buildset):
        report = yield g.generate(self.master, Mock(), key, buildset)
        return report

    @defer.inlineCallbacks
    def test_buildset_message_normal(self):
        g, build, buildset = yield self.setup_generator()
        report = yield self.buildset_message(g, buildset, [build])

        g.formatter.format_message_for_buildset.assert_called_with(
            self.master, buildset, [build], is_buildset=True, mode=("passing",), users=[]
        )

        # we retrieve build data differently when processing the buildset, so adjust it to match
        del build['buildrequest']
        del build['parentbuild']
        del build['parentbuilder']

        self.assertEqual(
            report,
            {
                "body": "body",
                "subject": "subject",
                "type": "text",
                "extra_info": None,
                "results": SUCCESS,
                "builds": [build],
                "buildset": buildset,
                "users": [],
                "patches": [],
                "logs": [],
            },
        )

    @defer.inlineCallbacks
    def test_buildset_message_no_builds(self):
        g, _, buildset = yield self.setup_generator(insert_build=False)
        report = yield self.buildset_message(g, buildset, [])

        g.formatter.format_message_for_buildset.assert_called_with(
            self.master, buildset, [], is_buildset=True, mode=("passing",), users=[]
        )

        self.assertEqual(
            report,
            {
                "body": "body",
                "subject": "subject",
                "type": "text",
                "extra_info": None,
                "results": SUCCESS,
                "builds": [],
                "buildset": buildset,
                "users": [],
                "patches": [],
                "logs": [],
            },
        )

    @defer.inlineCallbacks
    def test_buildset_message_no_result(self):
        g, build, buildset = yield self.setup_generator(results=None)
        buildset["results"] = None
        report = yield self.buildset_message(g, buildset, [build])

        g.formatter.format_message_for_buildset.assert_called_with(
            self.master, buildset, [build], is_buildset=True, mode=("passing",), users=[]
        )

        # we retrieve build data differently when processing the buildset, so adjust it to match
        del build['buildrequest']
        del build['parentbuild']
        del build['parentbuilder']

        self.assertEqual(
            report,
            {
                "body": "body",
                "subject": "subject",
                "type": "text",
                "extra_info": None,
                "results": None,
                "builds": [build],
                "buildset": buildset,
                "users": [],
                "patches": [],
                "logs": [],
            },
        )

    @defer.inlineCallbacks
    def test_buildset_message_no_builds_no_result(self):
        g, _, buildset = yield self.setup_generator(results=None, insert_build=False)
        buildset["results"] = None
        report = yield self.buildset_message(g, buildset, [])

        g.formatter.format_message_for_buildset.assert_called_with(
            self.master, buildset, [], is_buildset=True, mode=("passing",), users=[]
        )

        self.assertEqual(
            report,
            {
                "body": "body",
                "subject": "subject",
                "type": "text",
                "extra_info": None,
                "results": None,
                "builds": [],
                "buildset": buildset,
                "users": [],
                "patches": [],
                "logs": [],
            },
        )

    @defer.inlineCallbacks
    def test_buildset_message_no_result_formatter_no_subject(self):
        message = {
            "body": "body",
            "type": "text",
            "subject": None,  # deprecated unspecified subject
            "extra_info": None,
        }

        g, build, buildset = yield self.setup_generator(message=message)
        report = yield self.buildset_message(g, buildset, [build])

        g.formatter.format_message_for_buildset.assert_called_with(
            self.master, buildset, [build], is_buildset=True, mode=("passing",), users=[]
        )

        # we retrieve build data differently when processing the buildset, so adjust it to match
        del build['buildrequest']
        del build['parentbuild']
        del build['parentbuilder']

        self.assertEqual(
            report,
            {
                "body": "body",
                "subject": None,
                "type": "text",
                "extra_info": None,
                "results": SUCCESS,
                "builds": [build],
                "buildset": buildset,
                "users": [],
                "patches": [],
                "logs": [],
            },
        )

    @defer.inlineCallbacks
    def test_generate_complete(self):
        g, _, buildset = yield self.setup_generator(insert_build=False)
        report = yield self.generate(g, ("buildsets", 98, "complete"), buildset)

        self.assertEqual(
            report,
            {
                "body": "body",
                "subject": "subject",
                "type": "text",
                "extra_info": None,
                "results": SUCCESS,
                "builds": [],
                "buildset": buildset,
                "users": [],
                "patches": [],
                "logs": [],
            },
        )

    @defer.inlineCallbacks
    def test_generate_complete_with_builds(self):
        g, build, buildset = yield self.setup_generator(insert_build=True)
        report = yield self.generate(g, ("buildsets", 98, "complete"), buildset)

        # we retrieve build data differently when processing the buildset, so adjust it to match
        del build['buildrequest']
        del build['parentbuild']
        del build['parentbuilder']

        self.assertEqual(
            report,
            {
                "body": "body",
                "subject": "subject",
                "type": "text",
                "extra_info": None,
                "results": SUCCESS,
                "builds": [build],
                "buildset": buildset,
                "users": [],
                "patches": [],
                "logs": [],
            },
        )
