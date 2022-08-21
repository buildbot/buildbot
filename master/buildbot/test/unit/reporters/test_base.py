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


import mock

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.process.results import FAILURE
from buildbot.reporters.base import ReporterBase
from buildbot.reporters.generators.build import BuildStatusGenerator
from buildbot.reporters.generators.worker import WorkerMissingGenerator
from buildbot.reporters.message import MessageFormatter
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.util.config import ConfigErrorsMixin
from buildbot.test.util.logging import LoggingMixin
from buildbot.test.util.reporter import ReporterTestMixin


class TestException(Exception):
    pass


class TestReporterBase(ConfigErrorsMixin, TestReactorMixin, LoggingMixin,
                       unittest.TestCase, ReporterTestMixin):

    def setUp(self):
        self.setup_test_reactor()
        self.setup_reporter_test()
        self.setUpLogging()
        self.master = fakemaster.make_master(self, wantData=True, wantDb=True,
                                             wantMq=True)

    @defer.inlineCallbacks
    def setupNotifier(self, generators):
        mn = ReporterBase(generators=generators)
        mn.sendMessage = mock.Mock(spec=mn.sendMessage)
        mn.sendMessage.return_value = "<message>"
        yield mn.setServiceParent(self.master)
        yield mn.startService()
        return mn

    @defer.inlineCallbacks
    def setupBuildMessage(self, **kwargs):

        build = yield self.insert_build_finished(FAILURE)

        formatter = mock.Mock(spec=MessageFormatter)
        formatter.format_message_for_build.return_value = {
            "body": "body",
            "type": "text",
            "subject": "subject"
        }
        formatter.want_properties = False
        formatter.want_steps = False
        formatter.want_logs = False
        formatter.want_logs_content = False
        generator = BuildStatusGenerator(message_formatter=formatter, **kwargs)

        mn = yield self.setupNotifier(generators=[generator])

        yield mn._got_event(('builds', 20, 'finished'), build)
        return (mn, build, formatter)

    def setup_mock_generator(self, events_filter):
        gen = mock.Mock()
        gen.wanted_event_keys = events_filter
        gen.generate_name = lambda: '<name>'
        return gen

    def test_check_config_raises_error_when_generators_not_list(self):
        with self.assertRaisesConfigError('generators argument must be a list'):
            ReporterBase(generators='abc')

    @defer.inlineCallbacks
    def test_buildMessage_nominal(self):
        mn, build, formatter = yield self.setupBuildMessage(mode=("failing",))

        formatter.format_message_for_build.assert_called_with(self.master, build, is_buildset=False,
                                                              mode=('failing',), users=['me@foo'])

        report = {
            'body': 'body',
            'subject': 'subject',
            'type': 'text',
            'results': FAILURE,
            'builds': [build],
            'users': ['me@foo'],
            'patches': [],
            'logs': []
        }

        self.assertEqual(mn.sendMessage.call_count, 1)
        mn.sendMessage.assert_called_with([report])

    @defer.inlineCallbacks
    def test_worker_missing_sends_message(self):
        generator = WorkerMissingGenerator(workers=['myworker'])
        mn = yield self.setupNotifier(generators=[generator])

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

    @defer.inlineCallbacks
    def test_generator_throw_exception_on_generate(self):
        gen = self.setup_mock_generator([('fake1', None, None)])

        @defer.inlineCallbacks
        def generate_throw(*args, **kwargs):
            raise TestException()

        gen.generate = generate_throw

        notifier = yield self.setupNotifier(generators=[gen])

        yield notifier._got_event(('fake1', None, None), None)

        self.assertEqual(len(self.flushLoggedErrors(TestException)), 1)
        self.assertLogged('Got exception when handling reporter events')

    @defer.inlineCallbacks
    def test_reports_sent_in_order_despite_slow_generator(self):
        gen = self.setup_mock_generator([('fake1', None, None)])

        notifier = yield self.setupNotifier(generators=[gen])

        # Handle an event when generate is slow
        gen.generate = slow_generate = mock.Mock(return_value=defer.Deferred())
        notifier._got_event(('fake1', None, None), None)
        notifier.sendMessage.assert_not_called()

        # Then handle an event when generate is fast
        gen.generate = mock.Mock(return_value=defer.Deferred())
        gen.generate.return_value.callback(2)
        notifier._got_event(('fake1', None, None), None)

        # sendMessage still not called
        notifier.sendMessage.assert_not_called()

        # Have the slow generate finish
        slow_generate.return_value.callback(1)

        # Now sendMessage should have been called two times
        self.assertEqual(notifier.sendMessage.call_args_list, [mock.call([1]), mock.call([2])])

    @defer.inlineCallbacks
    def test_reconfig_waits_for_pending_events(self):
        gen = self.setup_mock_generator([('fake1', None, None)])
        gen.generate = mock.Mock(return_value=defer.Deferred())

        notifier = yield self.setupNotifier(generators=[gen])
        notifier._got_event(('fake1', None, None), None)
        self.assertIsNotNone(notifier._pending_got_event_call)

        d = notifier.reconfigService(generators=[gen])
        self.assertFalse(d.called)

        gen.generate.return_value.callback(1)
        self.assertTrue(d.called)
        self.assertIsNone(notifier._pending_got_event_call)
