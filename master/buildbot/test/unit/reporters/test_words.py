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

import re
from unittest import mock

from twisted.internet import reactor
from twisted.trial import unittest

from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.reporters import words
from buildbot.test import fakedb
from buildbot.test.fake import fakemaster
from buildbot.test.reactor import TestReactorMixin
from buildbot.util import datetime2epoch


class ContactMixin(TestReactorMixin):
    botClass = words.StatusBot

    channelClass = words.Channel
    contactClass = words.Contact
    USER = "me"
    CHANNEL = "#buildbot"

    BUILDER_NAMES = ['builder1', 'builder2']
    BUILDER_IDS = [23, 45]

    async def setUp(self):
        self.setup_test_reactor()
        self.patch(reactor, 'callLater', self.reactor.callLater)
        self.patch(reactor, 'seconds', self.reactor.seconds)
        self.patch(reactor, 'stop', self.reactor.stop)

        self.master = fakemaster.make_master(self, wantMq=True, wantData=True, wantDb=True)

        for builderid, name in zip(self.BUILDER_IDS, self.BUILDER_NAMES):
            self.master.db.builders.addTestBuilder(builderid=builderid, name=name)

        self.bot = self.botClass(notify_events={'success': 1, 'failure': 1})
        self.bot.channelClass = self.channelClass
        self.bot.contactClass = self.contactClass
        self.bot.nickname = 'nick'
        self.missing_workers = set()

        # fake out subscription/unsubscription
        self.subscribed = False

        # fake out clean shutdown
        self.bot.parent = self
        self.bot.master.botmaster = mock.Mock(name='StatusBot-instance.master.botmaster')
        self.bot.master.botmaster.shuttingDown = False

        def cleanShutdown():
            self.bot.master.botmaster.shuttingDown = True

        self.bot.master.botmaster.cleanShutdown = cleanShutdown

        def cancelCleanShutdown():
            self.bot.master.botmaster.shuttingDown = False

        self.bot.master.botmaster.cancelCleanShutdown = cancelCleanShutdown

        self.contact = self.contactClass(user=self.USER, channel=self.bot.getChannel(self.CHANNEL))
        await self.contact.channel.setServiceParent(self.master)
        await self.master.startService()

    def patch_send(self):
        self.sent = []

        def send(msg):
            if not isinstance(msg, (list, tuple)):
                msg = (msg,)
            for m in msg:
                self.sent.append(m)

        self.contact.channel.send = send

    async def do_test_command(
        self,
        command,
        args='',
        contact=None,
        clock_ticks=None,
        exp_usage=True,
        exp_UsageError=False,
        shuttingDown=False,
        **kwargs,
    ):
        if contact is None:
            contact = self.contact

        cmd = getattr(contact, 'command_' + command.upper())

        if exp_usage:
            self.assertTrue(hasattr(cmd, 'usage'))

        self.patch_send()
        self.bot.master.botmaster.shuttingDown = shuttingDown

        if exp_UsageError:
            try:
                await cmd(args, **kwargs)
            except words.UsageError:
                return
            else:
                self.fail("no UsageError")
        else:
            await cmd(args, **kwargs)
        if clock_ticks:
            self.reactor.pump(clock_ticks)

    def setupSomeBuilds(self):
        self.master.db.insert_test_data([
            # Three builds on builder#0, One build on builder#1
            fakedb.Build(
                id=13,
                masterid=88,
                workerid=13,
                builderid=self.BUILDER_IDS[0],
                buildrequestid=82,
                number=3,
            ),
            fakedb.Build(
                id=14,
                masterid=88,
                workerid=13,
                builderid=self.BUILDER_IDS[0],
                buildrequestid=83,
                number=4,
            ),
            fakedb.Build(
                id=15,
                masterid=88,
                workerid=13,
                builderid=self.BUILDER_IDS[1],
                buildrequestid=84,
                number=5,
            ),
            fakedb.Build(
                id=16,
                masterid=88,
                workerid=13,
                builderid=self.BUILDER_IDS[0],
                buildrequestid=85,
                number=6,
            ),
        ])
        self.master.db.builds.finishBuild(buildid=14, results=SUCCESS)

    def setup_multi_builders(self):
        # Make first builder configured, but not connected
        # Make second builder configured and connected
        self.master.db.insert_test_data([
            fakedb.Worker(id=1, name='linux1', info={}),  # connected one
            fakedb.Worker(id=2, name='linux2', info={}),  # disconnected one
            fakedb.BuilderMaster(id=4012, masterid=13, builderid=self.BUILDER_IDS[0]),
            fakedb.BuilderMaster(id=4013, masterid=13, builderid=self.BUILDER_IDS[1]),
            fakedb.ConfiguredWorker(id=14013, workerid=2, buildermasterid=4012),
            fakedb.ConfiguredWorker(id=14013, workerid=1, buildermasterid=4013),
        ])


class TestContact(ContactMixin, unittest.TestCase):
    def test_channel_service(self):
        self.assertTrue(self.contact.channel.running)
        self.contact.channel.stopService()

    async def test_command_notify0(self):
        await self.do_test_command('notify', exp_UsageError=True)
        await self.do_test_command('notify', args="invalid arg", exp_UsageError=True)
        await self.do_test_command('notify', args="on")
        self.assertEqual(self.sent, ["The following events are being notified: finished, started."])
        await self.do_test_command('notify', args="off")
        self.assertEqual(self.sent, ['No events are being notified.'])
        await self.do_test_command('notify', args="on started")
        self.assertEqual(self.sent, ["The following events are being notified: started."])
        await self.do_test_command('notify', args="off started")
        self.assertEqual(self.sent, ['No events are being notified.'])
        await self.assertFailure(self.do_test_command('notify', args="off finished"), KeyError)
        await self.do_test_command('notify', args="list")
        self.assertEqual(self.sent, ['No events are being notified.'])

    async def notify_build_test(self, notify_args):
        self.bot.tags = None
        await self.test_command_watch_builder0()
        await self.do_test_command('notify', args=notify_args)
        buildStarted = self.contact.channel.subscribed[0].callback
        buildFinished = self.contact.channel.subscribed[1].callback
        for buildid in (13, 14, 16):
            self.master.db.builds.finishBuild(buildid=buildid, results=SUCCESS)
            build = await self.master.data.get(('builds', buildid))
            buildStarted("somekey", build)
            buildFinished("somekey", build)

    def test_command_notify_build_started(self):
        self.notify_build_test("on started")

    def test_command_notify_build_finished(self):
        self.notify_build_test("on finished")

    def test_command_notify_build_better(self):
        self.notify_build_test("on better")

    def test_command_notify_build_worse(self):
        self.notify_build_test("on worse")

    def test_command_notify_build_problem(self):
        self.notify_build_test("on problem")

    def test_command_notify_build_recovery(self):
        self.notify_build_test("on recovery")

    def test_command_notify_build_started_finished(self):
        self.notify_build_test("on")

    async def test_notify_missing_worker(self):
        self.patch_send()
        await self.do_test_command('notify', args='on worker')
        missing_worker = self.contact.channel.subscribed[2].callback
        missing_worker(
            (None, None, 'missing'), {"workerid": 1, "name": 'work', "last_connection": 'sometime'}
        )
        self.assertEqual(self.sent[1], "Worker `work` is missing. It was seen last on sometime.")
        self.assertIn(1, self.contact.channel.missing_workers)

    async def test_notify_worker_is_back(self):
        self.patch_send()
        await self.do_test_command('notify', args='on worker')
        self.contact.channel.missing_workers.add(1)
        missing_worker = self.contact.channel.subscribed[2].callback
        missing_worker(
            (None, None, 'connected'),
            {"workerid": 1, "name": 'work', "last_connection": 'sometime'},
        )
        self.assertEqual(self.sent[1], "Worker `work` is back online.")
        self.assertNotIn(1, self.contact.channel.missing_workers)

    async def test_command_help_noargs(self):
        await self.do_test_command('help')
        self.assertIn('help - ', '\n'.join(self.sent))

    async def test_command_help_arg(self):
        self.contact.command_FOO = lambda: None
        self.contact.command_FOO.usage = 'foo - bar'
        await self.do_test_command('help', args='foo')
        self.assertIn('Usage: foo - bar', self.sent[0])

    async def test_command_help_no_usage(self):
        self.contact.command_FOO = lambda: None
        await self.do_test_command('help', args='foo')
        self.assertIn('No usage info for', self.sent[0])

    async def test_command_help_dict_command(self):
        self.contact.command_FOO = lambda: None
        self.contact.command_FOO.usage = {None: 'foo - bar'}
        await self.do_test_command('help', args='foo')
        self.assertIn('Usage: foo - bar', self.sent[0])

    async def test_command_help_dict_command_no_usage(self):
        self.contact.command_FOO = lambda: None
        self.contact.command_FOO.usage = {}
        await self.do_test_command('help', args='foo')
        self.assertIn("No usage info for 'foo'", self.sent[0])

    async def test_command_help_dict_command_arg(self):
        self.contact.command_FOO = lambda: None
        self.contact.command_FOO.usage = {'this': 'foo this - bar'}
        await self.do_test_command('help', args='foo this')
        self.assertIn('Usage: foo this - bar', self.sent[0])

    async def test_command_help_dict_command_arg_no_usage(self):
        self.contact.command_FOO = lambda: None
        self.contact.command_FOO.usage = {
            # nothing for arg 'this'
            ('this', 'first'): 'foo this first - bar'
        }
        await self.do_test_command('help', args='foo this')
        self.assertIn("No usage info for 'foo' 'this'", self.sent[0])

    async def test_command_help_dict_command_arg_subarg(self):
        self.contact.command_FOO = lambda: None
        self.contact.command_FOO.usage = {('this', 'first'): 'foo this first - bar'}
        await self.do_test_command('help', args='foo this first')
        self.assertIn('Usage: foo this first - bar', self.sent[0])

    async def test_command_help_dict_command_arg_subarg_no_usage(self):
        self.contact.command_FOO = lambda: None
        self.contact.command_FOO.usage = {
            None: 'foo - bar',
            'this': 'foo this - bar',
            ('this', 'first'): 'foo this first - bar',
            # nothing for subarg 'missing'
        }
        await self.do_test_command('help', args='foo this missing')
        self.assertIn("No usage info for 'foo' 'this' 'missing'", self.sent[0])

    async def test_command_help_nosuch(self):
        await self.do_test_command('help', args='foo', exp_UsageError=True)

    async def test_command_shutdown(self):
        await self.do_test_command('shutdown', exp_UsageError=True)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, False)

    async def test_command_shutdown_check_running(self):
        await self.do_test_command('shutdown', args='check', shuttingDown=False)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, False)
        self.assertIn('buildbot is running', self.sent[0])

    async def test_command_shutdown_check_shutting_down(self):
        await self.do_test_command('shutdown', args='check', shuttingDown=True)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, True)
        self.assertIn('buildbot is shutting down', self.sent[0])

    async def test_command_shutdown_start(self):
        await self.do_test_command('shutdown', args='start', shuttingDown=False)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, True)

    async def test_command_shutdown_stop(self):
        await self.do_test_command('shutdown', args='stop', shuttingDown=True)
        self.assertEqual(self.bot.master.botmaster.shuttingDown, False)

    async def test_command_shutdown_now(self):
        await self.do_test_command('shutdown', args='now')
        self.assertEqual(self.bot.master.botmaster.shuttingDown, False)
        self.assertTrue(self.reactor.stop_called)

    async def test_command_source(self):
        await self.do_test_command('source')
        self.assertIn('My source', self.sent[0])

    async def test_command_commands(self):
        await self.do_test_command('commands')
        self.assertIn('Buildbot commands', self.sent[0])

    async def test_command_hello(self):
        await self.do_test_command('hello', exp_usage=False)
        self.assertIn(self.sent[0], words.GREETINGS)

    async def test_command_list(self):
        await self.do_test_command('list', exp_UsageError=True)

    async def test_command_list_builders(self):
        await self.do_test_command('list', args='all builders')
        self.assertEqual(len(self.sent), 1)
        for builder in self.BUILDER_NAMES:
            self.assertIn(f'{builder} [offline]', self.sent[0])

    async def test_command_list_workers(self):
        workers = ['worker1', 'worker2']
        for worker in workers:
            self.master.db.workers.db.insert_test_data([fakedb.Worker(name=worker)])
        await self.do_test_command('list', args='all workers')
        self.assertEqual(len(self.sent), 1)
        for worker in workers:
            self.assertIn(f'{worker} [offline]', self.sent[0])

    async def test_command_list_workers_online(self):
        self.setup_multi_builders()
        # Also set the connectedness:
        self.master.db.insert_test_data([fakedb.ConnectedWorker(id=113, masterid=13, workerid=1)])
        await self.do_test_command('list', args='all workers')
        self.assertEqual(len(self.sent), 1)
        self.assertNotIn('linux1 [disconnected]', self.sent[0])
        self.assertIn('linux2 [disconnected]', self.sent[0])

    async def test_command_list_changes(self):
        self.master.db.workers.db.insert_test_data([fakedb.Change()])
        await self.do_test_command('list', args='2 changes')
        self.assertEqual(len(self.sent), 1)

    async def test_command_list_builders_not_connected(self):
        self.setup_multi_builders()

        await self.do_test_command('list', args='all builders')
        self.assertEqual(len(self.sent), 1)
        self.assertIn(f'{self.BUILDER_NAMES[0]} [offline]', self.sent[0])
        self.assertIn(f'{self.BUILDER_NAMES[1]} [offline]', self.sent[0])

    async def test_command_list_builders_connected(self):
        self.setup_multi_builders()
        # Also set the connectedness:
        self.master.db.insert_test_data([fakedb.ConnectedWorker(id=113, masterid=13, workerid=1)])

        await self.do_test_command('list', args='all builders')
        self.assertEqual(len(self.sent), 1)
        self.assertIn(f'{self.BUILDER_NAMES[0]} [offline]', self.sent[0])
        self.assertNotIn(f'{self.BUILDER_NAMES[1]} [offline]', self.sent[0])

    async def test_command_status(self):
        await self.do_test_command('status')

    async def test_command_status_online(self):
        # we are online and we have some finished builds
        self.setup_multi_builders()
        self.master.db.insert_test_data([
            fakedb.ConfiguredWorker(id=14012, workerid=1, buildermasterid=4013),
            fakedb.ConnectedWorker(id=114, masterid=13, workerid=1),
        ])
        self.setupSomeBuilds()
        self.master.db.builds.finishBuild(buildid=13, results=FAILURE)
        self.master.db.builds.finishBuild(buildid=15, results=SUCCESS)
        self.master.db.builds.finishBuild(buildid=16, results=FAILURE)
        await self.do_test_command('status')

    async def test_command_status_all(self):
        await self.do_test_command('status', args='all')

    async def test_command_status_builder0_offline(self):
        await self.do_test_command('status', args=self.BUILDER_NAMES[0])
        self.assertEqual(self.sent, [f'`{self.BUILDER_NAMES[0]}`: offline'])

    async def test_command_status_builder0_running(self):
        self.setupSomeBuilds()
        await self.do_test_command('status', args=self.BUILDER_NAMES[0])
        self.assertEqual(len(self.sent), 1)
        self.assertIn('`builder1`: running', self.sent[0])
        self.assertRegex(self.sent[0], r' build \[#3\].* \(no current step\)')
        self.assertRegex(self.sent[0], r' build \[#6\].* \(no current step\)')

    async def test_command_status_bogus(self):
        await self.do_test_command('status', args='bogus_builder', exp_UsageError=True)

    def sub_seconds(self, strings):
        # sometimes timing works out wrong, so just call it "n seconds"
        return [re.sub(r'\d seconds|a moment', 'N seconds', s) for s in strings]

    async def test_command_last(self):
        self.setupSomeBuilds()
        self.setup_multi_builders()
        # Also set the connectedness:
        self.master.db.insert_test_data([fakedb.ConnectedWorker(id=113, masterid=13, workerid=2)])
        await self.do_test_command('last')
        self.assertEqual(len(self.sent), 1)
        sent = self.sub_seconds(self.sent)
        self.assertIn('`builder1`: last build completed successfully (N seconds ago)', sent)

    async def test_command_last_all(self):
        self.setupSomeBuilds()
        await self.do_test_command('last', args='all')
        self.assertEqual(len(self.sent), 1)
        sent = self.sub_seconds(self.sent)
        self.assertIn('`builder1`: last build completed successfully (N seconds ago)', sent[0])
        self.assertIn('`builder2`: no builds run since last restart', sent[0])

    async def test_command_last_builder_bogus(self):
        await self.do_test_command('last', args="BOGUS", exp_UsageError=True)

    async def test_command_last_builder0(self):
        self.setupSomeBuilds()
        await self.do_test_command('last', args=self.BUILDER_NAMES[0])
        self.assertEqual(len(self.sent), 1)
        sent = self.sub_seconds(self.sent)
        self.assertIn('`builder1`: last build completed successfully (N seconds ago)', sent)

    async def test_command_last_builder1(self):
        self.setupSomeBuilds()
        await self.do_test_command('last', args=self.BUILDER_NAMES[1])
        self.assertEqual(len(self.sent), 1)
        self.assertIn('`builder2`: no builds run since last restart', self.sent)

    async def test_command_watch(self):
        await self.do_test_command('watch', exp_UsageError=True)

    async def test_command_watch_builder0_no_builds(self):
        await self.do_test_command('watch', args=self.BUILDER_NAMES[0])
        self.assertEqual(len(self.sent), 1)
        self.assertIn('There are no currently running builds.', self.sent[0])

    async def test_command_watch_builder0(self):
        self.setupSomeBuilds()
        await self.do_test_command('watch', args=self.BUILDER_NAMES[0])
        self.assertEqual(len(self.sent), 2)
        self.assertIn(
            'Watching build [#3](http://localhost:8080/#/builders/23/builds/3) of '
            '`builder1` until it finishes...',
            self.sent,
        )
        self.assertIn(
            'Watching build [#6](http://localhost:8080/#/builders/23/builds/6) of '
            '`builder1` until it finishes...',
            self.sent,
        )

    async def test_command_watch_builder0_get_notifications(self):
        # (continue from the prior test)
        self.bot.tags = None
        await self.test_command_watch_builder0()
        del self.sent[:]

        await self.sendBuildFinishedMessage(16)
        self.assertEqual(len(self.sent), 1)
        self.assertIn(
            "Build [#6](http://localhost:8080/#/builders/23/builds/6) of "
            "`builder1` completed successfully.",
            self.sent,
        )

    async def test_command_watch_builder1(self):
        self.setupSomeBuilds()
        await self.do_test_command('watch', args=self.BUILDER_NAMES[0])
        self.assertEqual(len(self.sent), 2)
        self.assertIn(
            'Watching build [#3](http://localhost:8080/#/builders/23/builds/3) of '
            '`builder1` until it finishes...',
            self.sent,
        )
        self.assertIn(
            'Watching build [#6](http://localhost:8080/#/builders/23/builds/6) of '
            '`builder1` until it finishes...',
            self.sent,
        )

    async def sendBuildFinishedMessage(self, buildid, results=0):
        self.master.db.builds.finishBuild(buildid=buildid, results=SUCCESS)
        build = await self.master.data.get(('builds', buildid))
        self.master.mq.callConsumer(
            ('builds', str(buildid), 'complete'),
            {
                "buildid": buildid,
                "number": build['number'],
                "builderid": build['builderid'],
                "buildrequestid": build['buildrequestid'],
                "workerid": build['workerid'],
                "masterid": build['masterid'],
                "started_at": datetime2epoch(build['started_at']),
                "complete": True,
                "complete_at": datetime2epoch(build['complete_at']),
                "state_string": '',
                "results": results,
            },
        )

    async def test_command_stop(self):
        await self.do_test_command('stop', exp_UsageError=True)

    async def test_command_stop_bogus_builder(self):
        await self.do_test_command(
            'stop', args="build BOGUS 'i have a reason'", exp_UsageError=True
        )

    async def test_command_stop_builder0_no_builds(self):
        await self.do_test_command('stop', args=f"build {self.BUILDER_NAMES[0]} 'i have a reason'")
        self.assertEqual(len(self.sent), 1)
        self.assertIn('no build is', self.sent[0])

    async def test_command_stop_builder0_1_builds(self):
        self.setupSomeBuilds()
        await self.do_test_command('stop', args=f"build {self.BUILDER_NAMES[0]} 'i have a reason'")
        self.assertEqual(len(self.sent), 2)
        self.assertRegex(self.sent[0], r'Build \[#[36]\].* of `builder1` interrupted')
        self.assertRegex(self.sent[1], r'Build \[#[63]\].* of `builder1` interrupted')

    async def test_command_force_no_args(self):
        await self.do_test_command('force', exp_UsageError=True)

    async def test_command_force_wrong_first_arg(self):
        await self.do_test_command('force', args='notbuild', exp_UsageError=True)

    async def test_command_force_build_no_args(self):
        await self.do_test_command('force', args='build', exp_UsageError=True)

    # TODO: missing tests for:
    #   - bad args
    #   - arg validation failure (self.master.config.validation)

    async def test_command_force(self):
        await self.do_test_command(
            'force',
            args=(
                'build --branch BRANCH1 --revision REV1 --props=PROP1=VALUE1 '
                f'{self.BUILDER_NAMES[0]} REASON'
            ),
        )

    async def test_handleMessage_short_command(self):
        self.contact.command_TESTY = mock.Mock()
        await self.contact.handleMessage('testy')

        self.contact.command_TESTY.assert_called_with('')

    async def test_handleMessage_long_command(self):
        self.contact.command_TESTY = mock.Mock()
        await self.contact.handleMessage('testy   westy boo')

        self.contact.command_TESTY.assert_called_with('westy boo')

    async def test_handleMessage_excited(self):
        self.patch_send()
        await self.contact.handleMessage('hi!')

        self.assertEqual(len(self.sent), 1)  # who cares what it says..

    async def test_handleMessage_exception(self):
        self.patch_send()

        def command_TESTY(msg):
            raise RuntimeError("FAIL")

        self.contact.command_TESTY = command_TESTY
        await self.contact.handleMessage('testy boom')

        self.assertEqual(self.sent, ["Something bad happened (see logs)"])
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

    async def test_handleMessage_UsageError(self):
        self.patch_send()

        def command_TESTY(msg):
            raise words.UsageError("oh noes")

        self.contact.command_TESTY = command_TESTY
        await self.contact.handleMessage('testy boom')

        self.assertEqual(self.sent, ["oh noes"])

    async def test_unclosed_quote(self):
        await self.do_test_command('list', args='args\'', exp_UsageError=True)
        await self.do_test_command('status', args='args\'', exp_UsageError=True)
        await self.do_test_command('notify', args='args\'', exp_UsageError=True)
        await self.do_test_command('watch', args='args\'', exp_UsageError=True)
        await self.do_test_command('force', args='args\'', exp_UsageError=True)
        await self.do_test_command('stop', args='args\'', exp_UsageError=True)
        await self.do_test_command('last', args='args\'', exp_UsageError=True)
        await self.do_test_command('help', args='args\'', exp_UsageError=True)

    async def test_buildStarted(self):
        self.setupSomeBuilds()
        self.patch_send()
        build = await self.master.data.get(('builds', 13))

        self.bot.tags = None
        self.contact.channel.notify_for = lambda _: True
        self.contact.useRevisions = False

        self.contact.channel.buildStarted(build)
        self.assertEqual(
            self.sent.pop(),
            "Build [#3](http://localhost:8080/#/builders/23/builds/3) of `builder1` started.",
        )

    def test_getCommandMethod_authz_default(self):
        self.bot.authz = words.StatusBot.expand_authz(None)
        meth = self.contact.getCommandMethod('shutdown')
        self.assertEqual(meth, self.contact.access_denied)

    authz1 = {
        'force': ['me'],
        'shutdown': ['notme', 'someone'],
        ('dance', 'notify'): True,
        '': False,
    }

    def test_getCommandMethod_explicit_allow(self):
        self.bot.authz = words.StatusBot.expand_authz(self.authz1)
        meth = self.contact.getCommandMethod('force')
        self.assertNotEqual(meth, self.contact.access_denied)

    def test_getCommandMethod_explicit_disallow(self):
        self.bot.authz = words.StatusBot.expand_authz(self.authz1)
        meth = self.contact.getCommandMethod('shutdown')
        self.assertEqual(meth, self.contact.access_denied)

    def test_getCommandMethod_explicit_multi(self):
        self.bot.authz = words.StatusBot.expand_authz(self.authz1)
        self.assertIn('DANCE', self.bot.authz)
        meth = self.contact.getCommandMethod('dance')
        self.assertNotEqual(meth, self.contact.access_denied)

    def test_getCommandMethod_explicit_default(self):
        self.bot.authz = words.StatusBot.expand_authz(self.authz1)
        meth = self.contact.getCommandMethod('help')
        self.assertEqual(meth, self.contact.access_denied)

    authz2 = {'shutdown': False, '': False, '*': True}

    def test_getCommandMethod_exclamation(self):
        self.bot.authz = words.StatusBot.expand_authz(self.authz2)
        meth = self.contact.getCommandMethod('help')
        self.assertNotEqual(meth, self.contact.access_denied)

    def test_getCommandMethod_exclamation_override(self):
        self.bot.authz = words.StatusBot.expand_authz(self.authz2)
        meth = self.contact.getCommandMethod('shutdown')
        self.assertEqual(meth, self.contact.access_denied)

    def test_access_denied(self):
        self.patch_send()
        self.contact.access_denied()
        self.assertIn("not pass", self.sent[0])

    async def test_bot_loadState(self):
        boid = await self.bot._get_object_id()
        self.master.db.insert_test_data([
            fakedb.ObjectState(
                objectid=boid, name='notify_events', value_json='[["#channel1", ["warnings"]]]'
            ),
        ])
        await self.bot.loadState()
        self.assertEqual(self.bot.channels['#channel1'].notify_events, {'warnings'})
