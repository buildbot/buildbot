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

from builtins import range

import mock
import os
import shutil

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.python import failure
from twisted.python import log
from twisted.trial import unittest

import buildslave

from buildslave import base
from buildslave import pb
from buildslave.test.fake.remote import FakeRemote
from buildslave.test.fake.runprocess import Expect
from buildslave.test.util import command
from buildslave.test.util import compat


class TestBot(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        self.real_bot = base.BotBase(self.basedir, False)
        self.real_bot.startService()

        self.bot = FakeRemote(self.real_bot)

    def tearDown(self):
        d = defer.succeed(None)
        if self.real_bot and self.real_bot.running:
            d.addCallback(lambda _: self.real_bot.stopService())
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        return d

    def test_getCommands(self):
        d = self.bot.callRemote("getCommands")

        def check(cmds):
            # just check that 'shell' is present..
            self.assertTrue('shell' in cmds)
        d.addCallback(check)
        return d

    def test_getVersion(self):
        d = self.bot.callRemote("getVersion")

        def check(vers):
            self.assertEqual(vers, buildslave.version)
        d.addCallback(check)
        return d

    def test_getSlaveInfo(self):
        infodir = os.path.join(self.basedir, "info")
        os.makedirs(infodir)
        open(os.path.join(infodir, "admin"), "w").write("testy!")
        open(os.path.join(infodir, "foo"), "w").write("bar")
        open(os.path.join(infodir, "environ"), "w").write("something else")

        d = self.bot.callRemote("getSlaveInfo")

        def check(info):
            self.assertEqual(info, dict(
                admin='testy!', foo='bar',
                environ=os.environ, system=os.name, basedir=self.basedir,
                slave_commands=self.real_bot.remote_getCommands(),
                version=self.real_bot.remote_getVersion()))
        d.addCallback(check)
        return d

    def test_getSlaveInfo_nodir(self):
        d = self.bot.callRemote("getSlaveInfo")

        def check(info):
            self.assertEqual(set(info.keys()), set(['environ', 'system', 'basedir', 'slave_commands', 'version']))
        d.addCallback(check)
        return d

    def test_setBuilderList_empty(self):
        d = self.bot.callRemote("setBuilderList", [])

        def check(builders):
            self.assertEqual(builders, {})
        d.addCallback(check)
        return d

    def test_setBuilderList_single(self):
        d = self.bot.callRemote("setBuilderList", [('mybld', 'myblddir')])

        def check(builders):
            self.assertEqual(list(builders), ['mybld'])
            self.assertTrue(os.path.exists(os.path.join(self.basedir, 'myblddir')))
            # note that we test the SlaveBuilder instance below
        d.addCallback(check)
        return d

    def test_setBuilderList_updates(self):
        d = defer.succeed(None)

        slavebuilders = {}

        def add_my(_):
            d = self.bot.callRemote("setBuilderList", [
                ('mybld', 'myblddir')])

            def check(builders):
                self.assertEqual(list(builders), ['mybld'])
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'myblddir')))
                slavebuilders['my'] = builders['mybld']
            d.addCallback(check)
            return d
        d.addCallback(add_my)

        def add_your(_):
            d = self.bot.callRemote("setBuilderList", [
                ('mybld', 'myblddir'), ('yourbld', 'yourblddir')])

            def check(builders):
                self.assertEqual(sorted(builders.keys()), sorted(['mybld', 'yourbld']))
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'myblddir')))
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'yourblddir')))
                # 'my' should still be the same slavebuilder object
                self.assertEqual(id(slavebuilders['my']), id(builders['mybld']))
                slavebuilders['your'] = builders['yourbld']
            d.addCallback(check)
            return d
        d.addCallback(add_your)

        def remove_my(_):
            d = self.bot.callRemote("setBuilderList", [
                ('yourbld', 'yourblddir2')])  # note new builddir

            def check(builders):
                self.assertEqual(sorted(builders.keys()), sorted(['yourbld']))
                # note that build dirs are not deleted..
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'myblddir')))
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'yourblddir')))
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'yourblddir2')))
                # 'your' should still be the same slavebuilder object
                self.assertEqual(id(slavebuilders['your']), id(builders['yourbld']))
            d.addCallback(check)
            return d
        d.addCallback(remove_my)

        def add_and_remove(_):
            d = self.bot.callRemote("setBuilderList", [
                ('theirbld', 'theirblddir')])

            def check(builders):
                self.assertEqual(sorted(builders.keys()), sorted(['theirbld']))
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'myblddir')))
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'yourblddir')))
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'theirblddir')))
            d.addCallback(check)
            return d
        d.addCallback(add_and_remove)

        return d

    def test_shutdown(self):
        d1 = defer.Deferred()
        self.patch(reactor, "stop", lambda: d1.callback(None))
        d2 = self.bot.callRemote("shutdown")
        # don't return until both the shutdown method has returned, and
        # reactor.stop has been called
        return defer.gatherResults([d1, d2])


class FakeStep(object):

    "A fake master-side BuildStep that records its activities."

    def __init__(self):
        self.finished_d = defer.Deferred()
        self.actions = []

    def wait_for_finish(self):
        return self.finished_d

    def remote_update(self, updates):
        for update in updates:
            if 'elapsed' in update[0]:
                update[0]['elapsed'] = 1
        self.actions.append(["update", updates])

    def remote_complete(self, f):
        self.actions.append(["complete", f])
        self.finished_d.callback(None)


class TestSlaveBuilder(command.CommandTestMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        self.bot = base.BotBase(self.basedir, False)
        self.bot.startService()

        # get a SlaveBuilder object from the bot and wrap it as a fake remote
        builders = yield self.bot.remote_setBuilderList([('sb', 'sb')])
        self.sb = FakeRemote(builders['sb'])

        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

        d = defer.succeed(None)
        if self.bot and self.bot.running:
            d.addCallback(lambda _: self.bot.stopService())
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        return d

    def test_print(self):
        return self.sb.callRemote("print", "Hello, SlaveBuilder.")

    def test_setMaster(self):
        # not much to check here - what the SlaveBuilder does with the
        # master is not part of the interface (and, in fact, it does very little)
        return self.sb.callRemote("setMaster", mock.Mock())

    def test_shutdown(self):
        # don't *actually* shut down the reactor - that would be silly
        stop = mock.Mock()
        self.patch(reactor, "stop", stop)
        d = self.sb.callRemote("shutdown")

        def check(_):
            self.assertTrue(stop.called)
        d.addCallback(check)
        return d

    def test_startBuild(self):
        return self.sb.callRemote("startBuild")

    def test_startCommand(self):
        # set up a fake step to receive updates
        st = FakeStep()

        # patch runprocess to handle the 'echo', below
        self.patch_runprocess(
            Expect(['echo', 'hello'], os.path.join(self.basedir, 'sb', 'workdir'))
            + {'hdr': 'headers'} + {'stdout': 'hello\n'} + {'rc': 0}
            + 0,
        )

        d = defer.succeed(None)

        def do_start(_):
            return self.sb.callRemote("startCommand", FakeRemote(st),
                                      "13", "shell", dict(
                                          command=['echo', 'hello'],
                                          workdir='workdir'))
        d.addCallback(do_start)
        d.addCallback(lambda _: st.wait_for_finish())

        def check(_):
            self.assertEqual(st.actions, [
                ['update', [[{'hdr': 'headers'}, 0]]],
                ['update', [[{'stdout': 'hello\n'}, 0]]],
                ['update', [[{'rc': 0}, 0]]],
                ['update', [[{'elapsed': 1}, 0]]],
                ['complete', None],
            ])
        d.addCallback(check)
        return d

    def test_startCommand_interruptCommand(self):
        # set up a fake step to receive updates
        st = FakeStep()

        # patch runprocess to pretend to sleep (it will really just hang forever,
        # except that we interrupt it)
        self.patch_runprocess(
            Expect(['sleep', '10'], os.path.join(self.basedir, 'sb', 'workdir'))
            + {'hdr': 'headers'}
            + {'wait': True}
        )

        d = defer.succeed(None)

        def do_start(_):
            return self.sb.callRemote("startCommand", FakeRemote(st),
                                      "13", "shell", dict(
                                          command=['sleep', '10'],
                                          workdir='workdir'))
        d.addCallback(do_start)

        # wait a jiffy..
        def do_wait(_):
            d = defer.Deferred()
            reactor.callLater(0.01, d.callback, None)
            return d
        d.addCallback(do_wait)

        # and then interrupt the step
        def do_interrupt(_):
            return self.sb.callRemote("interruptCommand", "13", "tl/dr")
        d.addCallback(do_interrupt)

        d.addCallback(lambda _: st.wait_for_finish())

        def check(_):
            self.assertEqual(st.actions, [
                ['update', [[{'hdr': 'headers'}, 0]]],
                ['update', [[{'hdr': 'killing'}, 0]]],
                ['update', [[{'rc': -1}, 0]]],
                ['complete', None],
            ])
        d.addCallback(check)
        return d

    def test_startCommand_failure(self):
        # set up a fake step to receive updates
        st = FakeStep()

        # patch runprocess to generate a failure
        self.patch_runprocess(
            Expect(['sleep', '10'], os.path.join(self.basedir, 'sb', 'workdir'))
            + failure.Failure(Exception("Oops"))
        )
        # patch the log.err, otherwise trial will think something *actually* failed
        self.patch(log, "err", lambda f: None)

        d = defer.succeed(None)

        def do_start(_):
            return self.sb.callRemote("startCommand", FakeRemote(st),
                                      "13", "shell", dict(
                                          command=['sleep', '10'],
                                          workdir='workdir'))
        d.addCallback(do_start)
        d.addCallback(lambda _: st.wait_for_finish())

        def check(_):
            self.assertEqual(st.actions[1][0], 'complete')
            self.assertTrue(isinstance(st.actions[1][1], failure.Failure))
        d.addCallback(check)
        return d

    def test_startCommand_missing_args(self):
        # set up a fake step to receive updates
        st = FakeStep()

        d = defer.succeed(None)

        def do_start(_):
            return self.sb.callRemote("startCommand", FakeRemote(st),
                                      "13", "shell", dict())
        d.addCallback(do_start)
        d.addCallback(lambda _: self.assertTrue(False))
        d.addErrback(lambda _: True)
        return d


class TestBotFactory(unittest.TestCase):

    def setUp(self):
        self.bf = pb.BotFactory('mstr', 9010, 35, 200)

    # tests

    def test_timers(self):
        clock = self.bf._reactor = task.Clock()

        calls = []

        def callRemote(method):
            calls.append(clock.seconds())
            self.assertEqual(method, 'keepalive')
            # simulate the response taking a few seconds
            d = defer.Deferred()
            clock.callLater(5, d.callback, None)
            return d
        self.bf.perspective = mock.Mock()
        self.bf.perspective.callRemote = callRemote

        self.bf.startTimers()
        clock.callLater(100, self.bf.stopTimers)

        clock.pump((1 for _ in range(150)))
        self.assertEqual(calls, [35, 70])

    @compat.usesFlushLoggedErrors
    def test_timers_exception(self):
        clock = self.bf._reactor = task.Clock()

        self.bf.perspective = mock.Mock()

        def callRemote(method):
            return defer.fail(RuntimeError("oh noes"))
        self.bf.perspective.callRemote = callRemote

        self.bf.startTimers()
        clock.advance(35)
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)

# note that the BuildSlave class is tested in test_bot_BuildSlave
