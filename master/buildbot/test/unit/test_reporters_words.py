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
from future.utils import iteritems

import re

import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.trial import unittest

from buildbot.process.results import SUCCESS
from buildbot.reporters import words
from buildbot.test.fake import fakedb
from buildbot.test.fake import fakemaster
from buildbot.util import datetime2epoch


class TestContactChannel(unittest.TestCase):

    BUILDER_NAMES = [u'builder1', u'builder2']
    BUILDER_IDS = [23, 45]

    def setUp(self):
        self.master = fakemaster.make_master(testcase=self, wantMq=True,
                                             wantData=True, wantDb=True)

        for builderid, name in zip(self.BUILDER_IDS, self.BUILDER_NAMES):
            self.master.db.builders.addTestBuilder(
                builderid=builderid, name=name)

        # I think the 'bot' part of this is actually going away ...
        # TO REMOVE:

        self.bot = mock.Mock(name='IRCStatusBot-instance')
        self.bot.nickname = 'nick'
        self.bot.notify_events = {'success': 1, 'failure': 1}
        self.bot.useRevisions = False
        self.bot.useColors = False

        # fake out subscription/unsubscription
        self.subscribed = False

        def subscribe(contact):
            self.subscribed = True
        self.bot.status.subscribe = subscribe

        def unsubscribe(contact):
            self.subscribed = False
        self.bot.status.unsubscribe = unsubscribe

        # fake out clean shutdown
        self.bot.master = self.master
        self.bot.master.botmaster = mock.Mock(
            name='IRCStatusBot-instance.master.botmaster')
        self.bot.master.botmaster.shuttingDown = False

        def cleanShutdown():
            self.bot.master.botmaster.shuttingDown = True
        self.bot.master.botmaster.cleanShutdown = cleanShutdown

        def cancelCleanShutdown():
            self.bot.master.botmaster.shuttingDown = False
        self.bot.master.botmaster.cancelCleanShutdown = cancelCleanShutdown

        self.contact = words.Contact(self.bot, user='me', channel='#buildbot')
        self.contact.setServiceParent(self.master)
        return self.master.startService()

    def patch_send(self):
        self.sent = []

        def send(msg):
            self.sent.append(msg)
        self.contact.send = send

    def patch_act(self):
        self.actions = []

        def act(msg):
            self.actions.append(msg)
        self.contact.act = act

    @defer.inlineCallbacks
    def do_test_command(self, command, args='', clock_ticks=None,
                        exp_usage=True, exp_UsageError=False, allowShutdown=False,
                        shuttingDown=False):
        cmd = getattr(self.contact, 'command_' + command.upper())

        if exp_usage:
            self.assertTrue(hasattr(cmd, 'usage'))

        clock = task.Clock()
        self.patch(reactor, 'callLater', clock.callLater)
        self.patch_send()
        self.patch_act()
        self.bot.factory.allowShutdown = allowShutdown
        self.bot.master.botmaster.shuttingDown = shuttingDown

        if exp_UsageError:
            try:
                yield cmd(args)
            except words.UsageError:
                return
            else:
                self.fail("no UsageError")
        else:
            cmd(args)
        if clock_ticks:
            clock.pump(clock_ticks)

    # tests

    def test_doSilly(self):
        clock = task.Clock()
        self.patch(reactor, 'callLater', clock.callLater)
        self.patch_send()
        silly_prompt, silly_response = list(iteritems(self.contact.silly))[0]

        self.contact.doSilly(silly_prompt)
        clock.pump([0.5] * 20)

        self.assertEqual(self.sent, silly_response)

    # TODO: remaining commands
    # (all depend on status, which interface will change soon)

    @defer.inlineCallbacks
    def test_command_mute(self):
        yield self.do_test_command('mute')
        self.assertTrue(self.contact.muted)

    @defer.inlineCallbacks
    def test_command_notify0(self):
        yield self.do_test_command('notify', exp_UsageError=True)
        yield self.do_test_command('notify', args="invalid arg", exp_UsageError=True)
        yield self.do_test_command('notify', args="on")
        self.assertEqual(
            self.sent, ["The following events are being notified: ['finished', 'started']"])
        yield self.do_test_command('notify', args="off")
        self.assertEqual(
            self.sent, ['The following events are being notified: []'])
        yield self.do_test_command('notify', args="on started")
        self.assertEqual(
            self.sent, ["The following events are being notified: ['started']"])
        yield self.do_test_command('notify', args="off started")
        self.assertEqual(
            self.sent, ['The following events are being notified: []'])
        yield self.assertFailure(
            self.do_test_command('notify', args="off finished"),
            KeyError)
        yield self.do_test_command('notify', args="list")
        self.assertEqual(
            self.sent, ['The following events are being notified: []'])

    @defer.inlineCallbacks
    def notify_build_test(self, notify_args):
        self.bot.tags = None
        yield self.test_command_watch_builder0()
        yield self.do_test_command('notify', args=notify_args)
        buildStarted = self.contact.subscribed[0].callback
        buildFinished = self.contact.subscribed[1].callback
        for buildid in (13, 14, 16):
            self.master.db.builds.finishBuild(buildid=buildid, results=SUCCESS)
            build = yield self.master.db.builds.getBuild(buildid)
            buildStarted("somekey", build)
            buildFinished("somekey", build)

    def test_command_notify_build_started(self):
        self.notify_build_test("on started")

    def test_command_notify_build_finished(self):
        self.notify_build_test("on finished")

    def test_command_notify_build_started_finished(self):
        self.notify_build_test("on")

    @defer.inlineCallbacks
    def test_command_unmute(self):
        self.contact.muted = True
        yield self.do_test_command('unmute')
        self.assertFalse(self.contact.muted)

    @defer.inlineCallbacks
    def test_command_unmute_not_muted(self):
        yield self.do_test_command('unmute')
        self.assertFalse(self.contact.muted)
        self.assertIn("hadn't told me to be quiet", self.sent[0])

    @defer.inlineCallbacks
    def test_command_help_noargs(self):
        yield self.do_test_command('help')
        self.assertIn('help on what', self.sent[0])

    @defer.inlineCallbacks
    def test_command_help_arg(self):
        self.contact.command_FOO = lambda: None
        self.contact.command_FOO.usage = 'foo - bar'
        yield self.do_test_command('help', args='foo')
        self.assertIn('Usage: foo - bar', self.sent[0])

    @defer.inlineCallbacks
    def test_command_help_no_usage(self):
        self.contact.command_FOO = lambda: None
        yield self.do_test_command('help', args='foo')
        self.assertIn('No usage info for', self.sent[0])

    @defer.inlineCallbacks
    def test_command_help_dict_command(self):
        self.contact.command_FOO = lambda: None
        self.contact.command_FOO.usage = {
            None: 'foo - bar'
        }
        yield self.do_test_command('help', args='foo')
        self.assertIn('Usage: foo - bar', self.sent[0])

    @defer.inlineCallbacks
    def test_command_help_dict_command_no_usage(self):
        self.contact.command_FOO = lambda: None
        self.contact.command_FOO.usage = {}
        yield self.do_test_command('help', args='foo')
        self.assertIn("No usage info for 'foo'", self.sent[0])

    @defer.inlineCallbacks
    def test_command_help_dict_command_arg(self):
        self.contact.command_FOO = lambda: None
        self.contact.command_FOO.usage = {
            'this': 'foo this - bar'
        }
        yield self.do_test_command('help', args='foo this')
        self.assertIn('Usage: foo this - bar', self.sent[0])

    @defer.inlineCallbacks
    def test_command_help_dict_command_arg_no_usage(self):
        self.contact.command_FOO = lambda: None
        self.contact.command_FOO.usage = {
            # nothing for arg 'this'
            ('this', 'first'): 'foo this first - bar'
        }
        yield self.do_test_command('help', args='foo this')
        self.assertIn("No usage info for 'foo' 'this'", self.sent[0])

    @defer.inlineCallbacks
    def test_command_help_dict_command_arg_subarg(self):
        self.contact.command_FOO = lambda: None
        self.contact.command_FOO.usage = {
            ('this', 'first'): 'foo this first - bar'
        }
        yield self.do_test_command('help', args='foo this first')
        self.assertIn('Usage: foo this first - bar', self.sent[0])

    @defer.inlineCallbacks
    def test_command_help_dict_command_arg_subarg_no_usage(self):
        self.contact.command_FOO = lambda: None
        self.contact.command_FOO.usage = {
            None: 'foo - bar',
            'this': 'foo this - bar',
            ('this', 'first'): 'foo this first - bar'
            # nothing for subarg 'missing'
        }
        yield self.do_test_command('help', args='foo this missing')
        self.assertIn("No usage info for 'foo' 'this' 'missing'", self.sent[0])

    @defer.inlineCallbacks
    def test_command_help_nosuch(self):
        yield self.do_test_command('help', args='foo', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_shutdown(self):
        yield self.do_test_command('shutdown', exp_UsageError=True)
        self.assertEqual(self.bot.factory.allowShutdown, False)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, False)

    @defer.inlineCallbacks
    def test_command_shutdown_dissalowed(self):
        yield self.do_test_command('shutdown', args='check', exp_UsageError=True)
        self.assertEqual(self.bot.factory.allowShutdown, False)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, False)

    @defer.inlineCallbacks
    def test_command_shutdown_check_running(self):
        yield self.do_test_command('shutdown', args='check', allowShutdown=True, shuttingDown=False)
        self.assertEqual(self.bot.factory.allowShutdown, True)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, False)
        self.assertIn('buildbot is running', self.sent[0])

    @defer.inlineCallbacks
    def test_command_shutdown_check_shutting_down(self):
        yield self.do_test_command('shutdown', args='check', allowShutdown=True, shuttingDown=True)
        self.assertEqual(self.bot.factory.allowShutdown, True)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, True)
        self.assertIn('buildbot is shutting down', self.sent[0])

    @defer.inlineCallbacks
    def test_command_shutdown_start(self):
        yield self.do_test_command('shutdown', args='start', allowShutdown=True, shuttingDown=False)
        self.assertEqual(self.bot.factory.allowShutdown, True)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, True)

    @defer.inlineCallbacks
    def test_command_shutdown_stop(self):
        yield self.do_test_command('shutdown', args='stop', allowShutdown=True, shuttingDown=True)
        self.assertEqual(self.bot.factory.allowShutdown, True)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, False)

    @defer.inlineCallbacks
    def test_command_shutdown_now(self):
        stop = mock.Mock()
        self.patch(reactor, 'stop', stop)
        yield self.do_test_command('shutdown', args='now', allowShutdown=True)
        self.assertEqual(self.bot.factory.allowShutdown, True)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, False)
        stop.assert_called_with()

    @defer.inlineCallbacks
    def test_command_source(self):
        yield self.do_test_command('source')
        self.assertIn('My source', self.sent[0])

    @defer.inlineCallbacks
    def test_command_commands(self):
        yield self.do_test_command('commands')
        self.assertIn('buildbot commands', self.sent[0])

    @defer.inlineCallbacks
    def test_command_destroy(self):
        yield self.do_test_command('destroy', exp_usage=False)
        self.assertEqual(self.actions, ['readies phasers'])

    @defer.inlineCallbacks
    def test_command_dance(self):
        yield self.do_test_command('dance', clock_ticks=[1.0] * 10, exp_usage=False)
        self.assertTrue(self.sent)  # doesn't matter what it sent

    @defer.inlineCallbacks
    def test_command_hustle(self):
        yield self.do_test_command('hustle', clock_ticks=[1.0] * 2, exp_usage=False)
        self.assertEqual(self.actions, ['does the hustle'])

    @defer.inlineCallbacks
    def test_command_hello(self):
        yield self.do_test_command('hello', exp_usage=False)
        self.assertEqual(self.sent, ['yes?'])
        yield self.do_test_command('hello', exp_usage=False)
        self.assertIn(self.sent[0], words.GREETINGS)

    @defer.inlineCallbacks
    def test_command_list(self):
        yield self.do_test_command('list', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_list_builders(self):
        yield self.do_test_command('list', args='builders')
        self.assertEqual(len(self.sent), 1)
        for builder in self.BUILDER_NAMES:
            self.assertIn('%s [offline]' % builder, self.sent[0])

    def setup_multi_builders(self):
        # Make first builder configured, but not connected
        # Make second builder configured and connected
        self.master.db.insertTestData([
            fakedb.Worker(id=1, name=u'linux', info={}),  # connected one
            fakedb.Worker(id=2, name=u'linux', info={}),  # disconnected one
            fakedb.BuilderMaster(
                id=4012, masterid=13, builderid=self.BUILDER_IDS[0]),
            fakedb.BuilderMaster(
                id=4013, masterid=13, builderid=self.BUILDER_IDS[1]),
            fakedb.ConfiguredWorker(id=14013,
                                    workerid=2, buildermasterid=4012),
            fakedb.ConfiguredWorker(id=14013,
                                    workerid=1, buildermasterid=4013),
        ])

    @defer.inlineCallbacks
    def test_command_list_builders_not_connected(self):
        self.setup_multi_builders()

        yield self.do_test_command('list', args='builders')
        self.assertEqual(len(self.sent), 1)
        self.assertIn('%s [offline]' % self.BUILDER_NAMES[0], self.sent[0])
        self.assertIn('%s [offline]' % self.BUILDER_NAMES[1], self.sent[0])

    @defer.inlineCallbacks
    def test_command_list_builders_connected(self):
        self.setup_multi_builders()

        # Also set the connectedness:
        self.master.db.insertTestData([
            fakedb.ConnectedWorker(id=113, masterid=13, workerid=1)
        ])

        yield self.do_test_command('list', args='builders')
        self.assertEqual(len(self.sent), 1)
        self.assertIn('%s [offline]' % self.BUILDER_NAMES[0], self.sent[0])
        self.assertNotIn('%s [offline]' % self.BUILDER_NAMES[1], self.sent[0])

    @defer.inlineCallbacks
    def test_command_status(self):
        yield self.do_test_command('status')

    @defer.inlineCallbacks
    def test_command_status_all(self):
        yield self.do_test_command('status', args='all')

    @defer.inlineCallbacks
    def test_command_status_builder0_offline(self):
        yield self.do_test_command('status', args=self.BUILDER_NAMES[0])
        self.assertEqual(self.sent, ['%s: offline' % self.BUILDER_NAMES[0]])

    @defer.inlineCallbacks
    def test_command_status_builder0_running(self):
        self.setupSomeBuilds()
        yield self.do_test_command('status', args=self.BUILDER_NAMES[0])
        self.assertEqual(len(self.sent), 1)
        self.assertIn('builder1: running', self.sent[0])
        self.assertIn(' 3 (no current step)', self.sent[0])
        self.assertIn(' 6 (no current step)', self.sent[0])

    @defer.inlineCallbacks
    def test_command_status_bogus(self):
        yield self.do_test_command('status', args='bogus_builder', exp_UsageError=True)

    def sub_seconds(self, strings):
        # sometimes timing works out wrong, so just call it "n seconds"
        return [re.sub(r'\d seconds', 'N seconds', s) for s in strings]

    @defer.inlineCallbacks
    def test_command_last(self):
        self.setupSomeBuilds()
        yield self.do_test_command('last')
        self.assertEqual(len(self.sent), 2)
        sent = self.sub_seconds(self.sent)
        self.assertIn(
            'last build [builder1]: last build N seconds ago: test', sent)
        self.assertIn(
            'last build [builder2]: (no builds run since last restart)', sent)

    @defer.inlineCallbacks
    def test_command_last_builder_bogus(self):
        yield self.do_test_command('last', args="BOGUS", exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_last_builder0(self):
        self.setupSomeBuilds()
        yield self.do_test_command('last', args=self.BUILDER_NAMES[0])
        self.assertEqual(len(self.sent), 1)
        sent = self.sub_seconds(self.sent)
        self.assertIn(
            'last build [builder1]: last build N seconds ago: test', sent)

    @defer.inlineCallbacks
    def test_command_last_builder1(self):
        self.setupSomeBuilds()
        yield self.do_test_command('last', args=self.BUILDER_NAMES[1])
        self.assertEqual(len(self.sent), 1)
        self.assertIn(
            'last build [builder2]: (no builds run since last restart)', self.sent)

    @defer.inlineCallbacks
    def test_command_watch(self):
        yield self.do_test_command('watch', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_watch_builder0_no_builds(self):
        yield self.do_test_command('watch', args=self.BUILDER_NAMES[0])
        self.assertEqual(len(self.sent), 1)
        self.assertIn('there are no builds', self.sent[0])

    def setupSomeBuilds(self):
        self.master.db.insertTestData([
            # Three builds on builder#0, One build on builder#1
            fakedb.Build(id=13, masterid=88, workerid=13,
                         builderid=self.BUILDER_IDS[0],
                         buildrequestid=82, number=3),
            fakedb.Build(id=14, masterid=88, workerid=13,
                         builderid=self.BUILDER_IDS[0],
                         buildrequestid=83, number=4),
            fakedb.Build(id=15, masterid=88, workerid=13,
                         builderid=self.BUILDER_IDS[1],
                         buildrequestid=84, number=5),
            fakedb.Build(id=16, masterid=88, workerid=13,
                         builderid=self.BUILDER_IDS[0],
                         buildrequestid=85, number=6),
        ])
        self.master.db.builds.finishBuild(buildid=14, results='results')

    @defer.inlineCallbacks
    def test_command_watch_builder0(self):
        self.setupSomeBuilds()
        yield self.do_test_command('watch', args=self.BUILDER_NAMES[0])
        self.assertEqual(len(self.sent), 2)
        self.assertIn(
            'watching build builder1 #3 until it finishes..', self.sent)
        self.assertIn(
            'watching build builder1 #6 until it finishes..', self.sent)

    @defer.inlineCallbacks
    def test_command_watch_builder0_get_notifications(self):
        # (continue from the prior test)
        self.bot.tags = None
        yield self.test_command_watch_builder0()
        del self.sent[:]

        yield self.sendBuildFinishedMessage(16)
        self.assertEqual(len(self.sent), 1)
        self.assertIn(
                "Build builder1 #6 is complete: Success [] - "
                "http://localhost:8080/#builders/23/builds/6", self.sent)

    @defer.inlineCallbacks
    def test_command_watch_builder1(self):
        self.setupSomeBuilds()
        yield self.do_test_command('watch', args=self.BUILDER_NAMES[0])
        self.assertEqual(len(self.sent), 2)
        self.assertIn(
            'watching build builder1 #3 until it finishes..', self.sent)
        self.assertIn(
            'watching build builder1 #6 until it finishes..', self.sent)

    @defer.inlineCallbacks
    def sendBuildFinishedMessage(self, buildid, results=0):
        self.master.db.builds.finishBuild(buildid=buildid, results=SUCCESS)
        build = yield self.master.db.builds.getBuild(buildid)
        self.master.mq.callConsumer(('builds', str(buildid), 'complete'),
                                    dict(
                                        buildid=buildid,
                                        number=build['number'],
                                        builderid=build['builderid'],
                                        buildrequestid=build['buildrequestid'],
                                        workerid=build['workerid'],
                                        masterid=build['masterid'],
                                        started_at=datetime2epoch(
                                            build['started_at']),
                                        complete=True,
                                        complete_at=datetime2epoch(
                                            build['complete_at']),
                                        state_string=u'',
                                        results=results,
        ))

    @defer.inlineCallbacks
    def test_command_stop(self):
        yield self.do_test_command('stop', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_stop_bogus_builder(self):
        yield self.do_test_command('stop', args="build BOGUS 'i have a reason'", exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_stop_builder0_no_builds(self):
        yield self.do_test_command('stop', args="build %s 'i have a reason'" % self.BUILDER_NAMES[0])
        self.assertEqual(len(self.sent), 1)
        self.assertIn('no build is', self.sent[0])

    @defer.inlineCallbacks
    def test_command_stop_builder0_1_builds(self):
        self.setupSomeBuilds()
        yield self.do_test_command('stop', args="build %s 'i have a reason'" % self.BUILDER_NAMES[0])
        self.assertEqual(len(self.sent), 2)
        self.assertIn('build 3 interrupted', self.sent)
        self.assertIn('build 6 interrupted', self.sent)

    @defer.inlineCallbacks
    def test_command_force_no_args(self):
        yield self.do_test_command('force', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_force_wrong_first_arg(self):
        yield self.do_test_command('force', args='notbuild', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_command_force_build_no_args(self):
        yield self.do_test_command('force', args='build', exp_UsageError=True)

    # TODO: missing tests for:
    #   - bad args
    #   - arg validation failure (self.master.config.validation)

    # TODO: the below fails due to the assertion (see "rewrite to not use the status hierarchy")
    # @defer.inlineCallbacks
    # def test_command_force(self):
    #     yield self.do_test_command('force',
    #             args='build --branch BRANCH1 --revision REV1 --props=PROP1=VALUE1 %s REASON'
    #               % self.BUILDER_NAMES[0])

    def test_send(self):
        events = []

        def groupChat(dest, msg):
            events.append((dest, msg))
        self.contact.bot.groupChat = groupChat

        self.contact.send("unmuted")
        self.contact.send(u"unmuted, unicode \N{SNOWMAN}")
        self.contact.muted = True
        self.contact.send("muted")

        self.assertEqual(events, [
            ('#buildbot', 'unmuted'),
            ('#buildbot', u'unmuted, unicode \u2603'),
        ])

    def test_act(self):
        events = []

        def groupDescribe(dest, msg):
            events.append((dest, msg))
        self.contact.bot.groupDescribe = groupDescribe

        self.contact.act("unmuted")
        self.contact.act(u"unmuted, unicode \N{SNOWMAN}")
        self.contact.muted = True
        self.contact.act("muted")

        self.assertEqual(events, [
            ('#buildbot', 'unmuted'),
            ('#buildbot', u'unmuted, unicode \u2603'),
        ])

    def test_handleMessage_silly(self):
        silly_prompt = list(self.contact.silly)[0]
        self.contact.doSilly = mock.Mock()
        d = self.contact.handleMessage(silly_prompt)

        @d.addCallback
        def cb(_):
            self.contact.doSilly.assert_called_with(silly_prompt)
        return d

    def test_handleMessage_short_command(self):
        self.contact.command_TESTY = mock.Mock()
        d = self.contact.handleMessage('testy')

        @d.addCallback
        def cb(_):
            self.contact.command_TESTY.assert_called_with('')
        return d

    def test_handleMessage_long_command(self):
        self.contact.command_TESTY = mock.Mock()
        d = self.contact.handleMessage('testy   westy boo')

        @d.addCallback
        def cb(_):
            self.contact.command_TESTY.assert_called_with('westy boo')
        return d

    def test_handleMessage_excited(self):
        self.patch_send()
        d = self.contact.handleMessage('hi!')

        @d.addCallback
        def cb(_):
            self.assertEqual(len(self.sent), 1)  # who cares what it says..
        return d

    def test_handleMessage_exception(self):
        self.patch_send()

        def command_TESTY(msg):
            raise RuntimeError("FAIL")
        self.contact.command_TESTY = command_TESTY
        d = self.contact.handleMessage('testy boom')

        @d.addCallback
        def cb(_):
            self.assertEqual(self.sent,
                             ["Something bad happened (see logs)"])
            self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)
        return d

    def test_handleMessage_UsageError(self):
        self.patch_send()

        def command_TESTY(msg):
            raise words.UsageError("oh noes")
        self.contact.command_TESTY = command_TESTY
        d = self.contact.handleMessage('testy boom')

        @d.addCallback
        def cb(_):
            self.assertEqual(self.sent, ["oh noes"])
        return d

    def test_handleAction_ignored(self):
        self.patch_act()
        self.contact.handleAction('waves hi')
        self.assertEqual(self.actions, [])

    def test_handleAction_kick(self):
        self.patch_act()
        self.contact.handleAction('kicks nick')
        self.assertEqual(self.actions, ['kicks back'])

    def test_handleAction_stupid(self):
        self.patch_act()
        self.contact.handleAction('stupids nick')
        self.assertEqual(self.actions, ['stupids me too'])

    @defer.inlineCallbacks
    def test_unclosed_quote(self):
        yield self.do_test_command('list', args='args\'', exp_UsageError=True)
        yield self.do_test_command('status', args='args\'', exp_UsageError=True)
        yield self.do_test_command('notify', args='args\'', exp_UsageError=True)
        yield self.do_test_command('watch', args='args\'', exp_UsageError=True)
        yield self.do_test_command('force', args='args\'', exp_UsageError=True)
        yield self.do_test_command('stop', args='args\'', exp_UsageError=True)
        yield self.do_test_command('last', args='args\'', exp_UsageError=True)
        yield self.do_test_command('help', args='args\'', exp_UsageError=True)

    @defer.inlineCallbacks
    def test_buildStarted(self):
        self.setupSomeBuilds()
        self.patch_send()
        build = yield self.master.db.builds.getBuild(13)

        self.bot.tags = None
        self.contact.notify_for = lambda _: True
        self.contact.useRevisions = False

        self.contact.buildStarted(build)
        self.assertEqual(
            self.sent.pop(),
            "build #3 of builder1 started")


class FakeContact(object):

    def __init__(self, bot, user=None, channel=None):
        self.bot = bot
        self.user = user
        self.channel = channel
        self.messages = []
        self.actions = []

    def handleMessage(self, message):
        self.messages.append(message)

    def handleAction(self, data):
        self.actions.append(data)
