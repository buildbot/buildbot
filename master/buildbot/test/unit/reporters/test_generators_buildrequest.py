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

from buildbot.process.builder import Builder
from buildbot.process.results import CANCELLED
from buildbot.reporters.generators.buildrequest import BuildRequestGenerator
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.reporter import ReporterTestMixin


class TestBuildRequestGenerator(ConfigErrorsMixin, TestReactorMixin,
                                unittest.TestCase, ReporterTestMixin):

    all_messages = ('failing', 'passing', 'warnings', 'exception', 'cancelled')

    def setUp(self):
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

        builder = Mock(spec=Builder)
        builder.master = self.master
        self.master.botmaster.getBuilderById = Mock(return_value=builder)

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
        g = BuildRequestGenerator(**kwargs)
        with self.assertRaisesConfigError('must be a list or None'):
            g.check()

    def setup_generator(self, message=None, **kwargs):
        if message is None:
            message = {
                "body": "start body",
                "type": "plain",
                "subject": "start subject"
            }

        g = BuildRequestGenerator(**kwargs)

        g.formatter = Mock(spec=g.formatter)
        g.formatter.format_message_for_build.return_value = message

        return g

    @defer.inlineCallbacks
    def test_build_message_start_no_result(self):
        g = yield self.setup_generator()
        buildrequest = yield self.insert_buildrequest_new()
        build = yield g.partial_build_dict(self.master, buildrequest)
        report = yield g.buildrequest_message(self.master, build)

        g.formatter.format_message_for_build.assert_called_with(self.master, build,
                                                                is_buildset=True,
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
    def test_build_message_add_patch(self):
        g = yield self.setup_generator(add_patch=True)
        buildrequest = yield self.insert_buildrequest_new(insert_patch=True)
        build = yield g.partial_build_dict(self.master, buildrequest)
        report = yield g.buildrequest_message(self.master, build)

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
        buildrequest = yield self.insert_buildrequest_new(insert_patch=False)
        build = yield g.partial_build_dict(self.master, buildrequest)
        report = yield g.buildrequest_message(self.master, build)
        self.assertEqual(report['patches'], [])

    @defer.inlineCallbacks
    def test_generate_new(self):
        g = yield self.setup_generator(add_patch=True)
        buildrequest = yield self.insert_buildrequest_new(insert_patch=False)
        build = yield g.partial_build_dict(self.master, buildrequest)
        report = yield g.generate(self.master, None, ('buildrequests', 11, 'new'), buildrequest)

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
    def test_generate_cancel(self):
        self.maxDiff = None
        g = yield self.setup_generator(add_patch=True)
        buildrequest = yield self.insert_buildrequest_new(insert_patch=False)
        build = yield g.partial_build_dict(self.master, buildrequest)
        report = yield g.generate(self.master, None, ('buildrequests', 11, 'cancel'), buildrequest)

        build['complete'] = True
        build['results'] = CANCELLED

        self.assertEqual(report, {
            'body': 'start body',
            'subject': 'start subject',
            'type': 'plain',
            'results': CANCELLED,
            'builds': [build],
            'users': [],
            'patches': [],
            'logs': []
        })

    @defer.inlineCallbacks
    def test_generate_none(self):
        g = BuildRequestGenerator(builders=['not_existing_builder'])
        buildrequest = yield self.insert_buildrequest_new()
        report = yield g.generate(self.master, None, ('buildrequests', 11, 'new'), buildrequest)

        self.assertIsNone(report, None)
