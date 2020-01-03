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
from future.builtins import range

import multiprocessing
import os
import shutil

import mock

from twisted.internet import defer
from twisted.internet import reactor
from twisted.internet import task
from twisted.python import failure
from twisted.python import log
from twisted.trial import unittest

import buildbot_worker
from buildbot_worker import base
from buildbot_worker import pb
from buildbot_worker.commands.base import Command
from buildbot_worker.test.fake.remote import FakeRemote
from buildbot_worker.test.fake.runprocess import Expect
from buildbot_worker.test.util import command
from buildbot_worker.test.util import compat


class TestBot(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        # create test-release-file
        with open("%s/test-release-file" % self.basedir, "w") as fout:
            fout.write(
"""
# unit test release file
OS_NAME="Test"
VERSION="1.0"
ID=test
ID_LIKE=generic
PRETTY_NAME="Test 1.0 Generic"
VERSION_ID="1"
"""
            )
        self.real_bot = base.BotBase(self.basedir, False)
        self.real_bot.setOsReleaseFile("%s/test-release-file" % self.basedir)
        self.real_bot.startService()

        self.bot = FakeRemote(self.real_bot)

    @defer.inlineCallbacks
    def tearDown(self):
        if self.real_bot and self.real_bot.running:
            yield self.real_bot.stopService()
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

    @defer.inlineCallbacks
    def test_getCommands(self):
        cmds = yield self.bot.callRemote("getCommands")

        # just check that 'shell' is present..
        self.assertTrue('shell' in cmds)

    @defer.inlineCallbacks
    def test_getVersion(self):
        vers = yield self.bot.callRemote("getVersion")

        self.assertEqual(vers, buildbot_worker.version)

    @defer.inlineCallbacks
    def test_getWorkerInfo(self):
        infodir = os.path.join(self.basedir, "info")
        os.makedirs(infodir)
        with open(os.path.join(infodir, "admin"), "w") as f:
            f.write("testy!")
        with open(os.path.join(infodir, "foo"), "w") as f:
            f.write("bar")
        with open(os.path.join(infodir, "environ"), "w") as f:
            f.write("something else")

        info = yield self.bot.callRemote("getWorkerInfo")

        # remove any os_ fields as they are dependent on the test environment
        info = {k: v for k, v in info.items() if not k.startswith("os_")}

        self.assertEqual(info, dict(
            admin='testy!', foo='bar',
            environ=os.environ, system=os.name, basedir=self.basedir,
            worker_commands=self.real_bot.remote_getCommands(),
            version=self.real_bot.remote_getVersion(),
            numcpus=multiprocessing.cpu_count()))

    @defer.inlineCallbacks
    def test_getWorkerInfo_nodir(self):
        info = yield self.bot.callRemote("getWorkerInfo")

        info = {k: v for k, v in info.items() if not k.startswith("os_")}

        self.assertEqual(set(info.keys()), set(
            ['environ', 'system', 'numcpus', 'basedir', 'worker_commands', 'version']))

    @defer.inlineCallbacks
    def test_setBuilderList_empty(self):
        builders = yield self.bot.callRemote("setBuilderList", [])

        self.assertEqual(builders, {})

    @defer.inlineCallbacks
    def test_setBuilderList_single(self):
        builders = yield self.bot.callRemote("setBuilderList", [('mybld', 'myblddir')])

        self.assertEqual(list(builders), ['mybld'])
        self.assertTrue(
            os.path.exists(os.path.join(self.basedir, 'myblddir')))
        # note that we test the WorkerForBuilder instance below

    @defer.inlineCallbacks
    def test_setBuilderList_updates(self):

        workerforbuilders = {}

        builders = yield self.bot.callRemote("setBuilderList", [
            ('mybld', 'myblddir')])

        self.assertEqual(list(builders), ['mybld'])
        self.assertTrue(
            os.path.exists(os.path.join(self.basedir, 'myblddir')))
        workerforbuilders['my'] = builders['mybld']

        builders = yield self.bot.callRemote("setBuilderList", [
            ('mybld', 'myblddir'), ('yourbld', 'yourblddir')])

        self.assertEqual(
            sorted(builders.keys()), sorted(['mybld', 'yourbld']))
        self.assertTrue(
            os.path.exists(os.path.join(self.basedir, 'myblddir')))
        self.assertTrue(
            os.path.exists(os.path.join(self.basedir, 'yourblddir')))
        # 'my' should still be the same WorkerForBuilder object
        self.assertEqual(
            id(workerforbuilders['my']), id(builders['mybld']))
        workerforbuilders['your'] = builders['yourbld']
        self.assertTrue(repr(workerforbuilders['your']).startswith(
                         "<WorkerForBuilder 'yourbld' at "))

        builders = yield self.bot.callRemote("setBuilderList", [
            ('yourbld', 'yourblddir2')])  # note new builddir

        self.assertEqual(sorted(builders.keys()), sorted(['yourbld']))
        # note that build dirs are not deleted..
        self.assertTrue(
            os.path.exists(os.path.join(self.basedir, 'myblddir')))
        self.assertTrue(
            os.path.exists(os.path.join(self.basedir, 'yourblddir')))
        self.assertTrue(
            os.path.exists(os.path.join(self.basedir, 'yourblddir2')))
        # 'your' should still be the same WorkerForBuilder object
        self.assertEqual(
            id(workerforbuilders['your']), id(builders['yourbld']))

        builders = yield self.bot.callRemote("setBuilderList", [
                ('theirbld', 'theirblddir')])

        self.assertEqual(sorted(builders.keys()), sorted(['theirbld']))
        self.assertTrue(
            os.path.exists(os.path.join(self.basedir, 'myblddir')))
        self.assertTrue(
            os.path.exists(os.path.join(self.basedir, 'yourblddir')))
        self.assertTrue(
            os.path.exists(os.path.join(self.basedir, 'theirblddir')))

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


class TestWorkerForBuilder(command.CommandTestMixin, unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        self.bot = base.BotBase(self.basedir, False)
        self.bot.startService()

        # get a WorkerForBuilder object from the bot and wrap it as a fake
        # remote
        builders = yield self.bot.remote_setBuilderList([('wfb', 'wfb')])
        self.wfb = FakeRemote(builders['wfb'])

        self.setUpCommand()

    @defer.inlineCallbacks
    def tearDown(self):
        self.tearDownCommand()

        if self.bot and self.bot.running:
            yield self.bot.stopService()
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

    def test_print(self):
        return self.wfb.callRemote("print", "Hello, WorkerForBuilder.")

    def test_printWithCommand(self):
        self.wfb.original.command = Command("builder", "1", ["arg1", "arg2"])
        return self.wfb.callRemote("print", "Hello again, WorkerForBuilder.")

    def test_setMaster(self):
        # not much to check here - what the WorkerForBuilder does with the
        # master is not part of the interface (and, in fact, it does very
        # little)
        return self.wfb.callRemote("setMaster", mock.Mock())

    def test_startBuild(self):
        return self.wfb.callRemote("startBuild")

    @defer.inlineCallbacks
    def test_startCommand(self):
        # set up a fake step to receive updates
        st = FakeStep()

        # patch runprocess to handle the 'echo', below
        self.patch_runprocess(
            Expect(['echo', 'hello'], os.path.join(
                self.basedir, 'wfb', 'workdir')) +
            {'hdr': 'headers'} +
            {'stdout': 'hello\n'} +
            {'rc': 0} +
            0,
        )

        yield self.wfb.callRemote("startCommand", FakeRemote(st),
                                  "13", "shell", dict(command=['echo', 'hello'],
                                                      workdir='workdir'))
        yield st.wait_for_finish()

        def check(_):
            self.assertEqual(st.actions, [
                ['update', [[{'hdr': 'headers'}, 0]]],
                ['update', [[{'stdout': 'hello\n'}, 0]]],
                ['update', [[{'rc': 0}, 0]]],
                ['update', [[{'elapsed': 1}, 0]]],
                ['complete', None],
            ])

    @defer.inlineCallbacks
    def test_startCommand_interruptCommand(self):
        # set up a fake step to receive updates
        st = FakeStep()

        # patch runprocess to pretend to sleep (it will really just hang forever,
        # except that we interrupt it)
        self.patch_runprocess(
            Expect(['sleep', '10'], os.path.join(
                self.basedir, 'wfb', 'workdir')) +
            {'hdr': 'headers'} +
            {'wait': True}
        )

        yield self.wfb.callRemote("startCommand", FakeRemote(st),
                                  "13", "shell", dict(command=['sleep', '10'],
                                                      workdir='workdir'))

        # wait a jiffy..
        d = defer.Deferred()
        reactor.callLater(0.01, d.callback, None)
        yield d

        # and then interrupt the step
        yield self.wfb.callRemote("interruptCommand", "13", "tl/dr")

        yield st.wait_for_finish()

        self.assertEqual(st.actions, [
            ['update', [[{'hdr': 'headers'}, 0]]],
            ['update', [[{'hdr': 'killing'}, 0]]],
            ['update', [[{'rc': -1}, 0]]],
            ['complete', None],
        ])

    @defer.inlineCallbacks
    def test_startCommand_failure(self):
        # set up a fake step to receive updates
        st = FakeStep()

        # patch runprocess to generate a failure
        self.patch_runprocess(
            Expect(['sleep', '10'], os.path.join(
                self.basedir, 'wfb', 'workdir')) +
            failure.Failure(Exception("Oops"))
        )
        # patch the log.err, otherwise trial will think something *actually*
        # failed
        self.patch(log, "err", lambda f: None)

        yield self.wfb.callRemote("startCommand", FakeRemote(st),
                                  "13", "shell", dict(command=['sleep', '10'],
                                                      workdir='workdir'))

        yield st.wait_for_finish()

        self.assertEqual(st.actions[1][0], 'complete')
        self.assertTrue(isinstance(st.actions[1][1], failure.Failure))

    @defer.inlineCallbacks
    def test_startCommand_missing_args(self):
        # set up a fake step to receive updates
        st = FakeStep()

        def do_start():
            return self.wfb.callRemote("startCommand", FakeRemote(st),
                                       "13", "shell", dict())

        yield self.assertFailure(do_start(), ValueError)

    @defer.inlineCallbacks
    def test_startCommand_invalid_command(self):
        # set up a fake step to receive updates
        st = FakeStep()

        def do_start():
            return self.wfb.callRemote("startCommand", FakeRemote(st),
                                       "13", "invalid command", dict())

        unknownCommand = yield self.assertFailure(do_start(), base.UnknownCommand)
        self.assertEqual(str(unknownCommand), "unrecognized WorkerCommand 'invalid command'")


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

# note that the Worker class is tested in test_bot_Worker
