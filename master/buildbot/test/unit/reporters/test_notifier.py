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

import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.reporters.generators.worker import WorkerMissingGenerator
from buildbot.reporters.message import MessageFormatter
from buildbot.reporters.notifier import NotifierBase
from buildbot.test.fake import fakemaster
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.misc import TestReactorMixin
from buildbot.test.util.notifier import NotifierTestMixin
from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.warnings import DeprecatedApiWarning


class TestNotifierBase(ConfigErrorsMixin, TestReactorMixin,
                       unittest.TestCase, NotifierTestMixin):

    def setUp(self):
        self.setUpTestReactor()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

    @defer.inlineCallbacks
    def setupNotifier(self, old_style=False, *args, **kwargs):
        if old_style:
            with assertProducesWarnings(DeprecatedApiWarning,
                                        message_pattern='have been deprecated'):
                mn = NotifierBase(*args, **kwargs)
        else:
            if 'generators' not in kwargs:
                if 'watchedWorkers' in kwargs:
                    generator = WorkerMissingGenerator(workers=kwargs.pop('watchedWorkers'))
                    kwargs['generators'] = [generator]

            mn = NotifierBase(*args, **kwargs)

        mn.sendMessage = mock.Mock(spec=mn.sendMessage)
        mn.sendMessage.return_value = "<message>"
        yield mn.setServiceParent(self.master)
        yield mn.startService()
        return mn

    @defer.inlineCallbacks
    def setupBuildMessage(self, old_style=False, **mnKwargs):

        _, builds = yield self.setupBuildResults(FAILURE)

        formatter = mock.Mock(spec=MessageFormatter)
        formatter.formatMessageForBuildResults.return_value = {"body": "body",
                                                               "type": "text",
                                                               "subject": "subject"}
        formatter.wantProperties = False
        formatter.wantSteps = False
        formatter.wantLogs = False

        if old_style:
            with assertProducesWarnings(DeprecatedApiWarning,
                                        message_pattern='have been deprecated'):
                mn = yield self.setupNotifier(old_style=True, messageFormatter=formatter,
                                              **mnKwargs)
        else:
            generator_kwargs = {}
            if 'mode' in mnKwargs:
                generator_kwargs['mode'] = mnKwargs.pop('mode')
            generator = BuildStatusGenerator(message_formatter=formatter, **generator_kwargs)

            mn = yield self.setupNotifier(generators=[generator], **mnKwargs)

        yield mn._got_event(('builds', 97, 'finished'), builds[0])
        return (mn, builds, formatter)

    def setup_mock_generator(self, events_filter):
        gen = mock.Mock()
        gen.wanted_event_keys = events_filter
        gen.generate_name = lambda: '<name>'
        return gen

    @parameterized.expand([
        ('mode', ('failing',)),
        ('tags', ['tag']),
        ('builders', ['builder']),
        ('buildSetSummary', True),
        ('messageFormatter', mock.Mock()),
        ('subject', 'custom subject'),
        ('addLogs', True),
        ('addPatch', True),
        ('schedulers', ['scheduler']),
        ('branches', ['branch']),
        ('watchedWorkers', ['worker']),
        ('messageFormatterMissingWorker', mock.Mock()),
    ])
    def test_check_config_raises_error_when_deprecated_and_generator(self, arg_name, arg_value):
        notifier = NotifierBase()
        with assertProducesWarnings(DeprecatedApiWarning, message_pattern='have been deprecated'):
            with self.assertRaisesConfigError('can\'t specify generators and deprecated notifier'):
                kwargs = {arg_name: arg_value}
                notifier.checkConfig(generators=[mock.Mock()], **kwargs)

    @parameterized.expand([
        ('mode', ('failing',)),
        ('tags', ['tag']),
        ('builders', ['builder']),
        ('buildSetSummary', True),
        ('messageFormatter', mock.Mock()),
        ('subject', 'custom subject'),
        ('addLogs', True),
        ('addPatch', True),
        ('schedulers', ['scheduler']),
        ('branches', ['branch']),
        ('watchedWorkers', ['worker']),
        ('messageFormatterMissingWorker', mock.Mock()),
    ])
    def test_check_config_raises_warning_when_deprecated(self, arg_name, arg_value):
        notifier = NotifierBase()
        with assertProducesWarnings(DeprecatedApiWarning, message_pattern='have been deprecated'):
            kwargs = {arg_name: arg_value}
            notifier.checkConfig(**kwargs)

    @parameterized.expand([
        ('_old_style', True),
        ('_new_style', False),
    ])
    @defer.inlineCallbacks
    def test_buildMessage_nominal(self, name, old_style):
        mn, builds, formatter = yield self.setupBuildMessage(old_style=old_style, mode=("change",))

        build = builds[0]
        formatter.formatMessageForBuildResults.assert_called_with(
            ('change',), 'Builder1', build['buildset'], build, self.master, SUCCESS, ['me@foo'])

        report = {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
            'builder_name': 'Builder1',
            'results': FAILURE,
            'builds': builds,
            'users': ['me@foo'],
            'patches': [],
            'logs': []
        }

        self.assertEqual(mn.sendMessage.call_count, 1)
        mn.sendMessage.assert_called_with([report])

    @parameterized.expand([
        ('_old_style', True),
        ('_new_style', False),
    ])
    @defer.inlineCallbacks
    def test_worker_missing_sends_message(self, name, old_style):

        mn = yield self.setupNotifier(old_style=old_style, watchedWorkers=['myworker'])

        worker_dict = {
            'name': 'myworker',
            'notify': ["workeradmin@example.org"],
            'workerinfo': {"admin": "myadmin"},
            'last_connection': "yesterday"
        }
        yield mn._got_event(('workers', 98, 'missing'), worker_dict)

        self.assertEqual(mn.sendMessage.call_count, 1)

    @defer.inlineCallbacks
    def test_generators_subscribes_events(self):
        gen1 = self.setup_mock_generator([('fake1', None, None)])

        yield self.setupNotifier(generators=[gen1])
        self.assertEqual(len(self.master.mq.qrefs), 1)
        self.assertEqual(self.master.mq.qrefs[0].filter, ('fake1', None, None))

    @defer.inlineCallbacks
    def test_generators_subscribes_equal_events_once(self):
        gen1 = self.setup_mock_generator([('fake1', None, None)])
        gen2 = self.setup_mock_generator([('fake1', None, None)])

        yield self.setupNotifier(generators=[gen1, gen2])
        self.assertEqual(len(self.master.mq.qrefs), 1)
        self.assertEqual(self.master.mq.qrefs[0].filter, ('fake1', None, None))

    @defer.inlineCallbacks
    def test_generators_subscribes_equal_different_events_once(self):
        gen1 = self.setup_mock_generator([('fake1', None, None)])
        gen2 = self.setup_mock_generator([('fake2', None, None)])

        yield self.setupNotifier(generators=[gen1, gen2])
        self.assertEqual(len(self.master.mq.qrefs), 2)
        self.assertEqual(self.master.mq.qrefs[0].filter, ('fake1', None, None))
        self.assertEqual(self.master.mq.qrefs[1].filter, ('fake2', None, None))

    @defer.inlineCallbacks
    def test_generators_unsubscribes_on_stop_service(self):
        gen1 = self.setup_mock_generator([('fake1', None, None)])

        notifier = yield self.setupNotifier(generators=[gen1])
        yield notifier.stopService()
        self.assertEqual(len(self.master.mq.qrefs), 0)

    @defer.inlineCallbacks
    def test_generators_resubscribes_on_reconfig(self):
        gen1 = self.setup_mock_generator([('fake1', None, None)])
        gen2 = self.setup_mock_generator([('fake2', None, None)])

        notifier = yield self.setupNotifier(generators=[gen1])
        self.assertEqual(len(self.master.mq.qrefs), 1)
        self.assertEqual(self.master.mq.qrefs[0].filter, ('fake1', None, None))

        yield notifier.reconfigService(generators=[gen2])
        self.assertEqual(len(self.master.mq.qrefs), 1)
        self.assertEqual(self.master.mq.qrefs[0].filter, ('fake2', None, None))
