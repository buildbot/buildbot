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
from __future__ import annotations

import multiprocessing
import os
import shutil
from typing import TYPE_CHECKING
from typing import cast

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

try:
    from unittest import mock
except ImportError:
    from unittest import mock

if TYPE_CHECKING:
    from typing import Any
    from typing import Iterable
    from typing import Sequence

    from twisted.internet.interfaces import IReactorTime

    from buildbot_worker.util.twisted import InlineCallbacksType


class TestBot(unittest.TestCase):
    def setUp(self) -> None:
        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        # create test-release-file
        with open(f"{self.basedir}/test-release-file", "w") as fout:
            fout.write("""
# unit test release file
OS_NAME="Test"
VERSION="1.0"
ID=test
ID_LIKE=generic
PRETTY_NAME="Test 1.0 Generic"
VERSION_ID="1"
""")
        self.real_bot = pb.BotPbLike(self.basedir)
        self.real_bot.setOsReleaseFile(f"{self.basedir}/test-release-file")
        self.real_bot.startService()
        self.addCleanup(self.real_bot.stopService)

        self.bot = FakeRemote(self.real_bot)

    def tearDown(self) -> None:
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

    @defer.inlineCallbacks
    def test_getCommands(self) -> InlineCallbacksType[None]:
        cmds = yield self.bot.callRemote("getCommands")

        # just check that 'shell' is present..
        self.assertTrue('shell' in cmds)

    @defer.inlineCallbacks
    def test_getVersion(self) -> InlineCallbacksType[None]:
        vers = yield self.bot.callRemote("getVersion")

        self.assertEqual(vers, buildbot_worker.version)

    @defer.inlineCallbacks
    def test_getWorkerInfo(self) -> InlineCallbacksType[None]:
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

        self.assertEqual(
            info,
            {
                "admin": 'testy!',
                "foo": 'bar',
                "environ": os.environ,
                "system": os.name,
                "basedir": self.basedir,
                "worker_commands": self.real_bot.remote_getCommands(),
                "version": self.real_bot.remote_getVersion(),
                "numcpus": multiprocessing.cpu_count(),
                "delete_leftover_dirs": False,
            },
        )

    @defer.inlineCallbacks
    def test_getWorkerInfo_nodir(self) -> InlineCallbacksType[None]:
        info = yield self.bot.callRemote("getWorkerInfo")

        info = {k: v for k, v in info.items() if not k.startswith("os_")}

        self.assertEqual(
            set(info.keys()),
            set([
                'environ',
                'system',
                'numcpus',
                'basedir',
                'worker_commands',
                'version',
                'delete_leftover_dirs',
            ]),
        )

    @defer.inlineCallbacks
    def test_getWorkerInfo_decode_error(self) -> InlineCallbacksType[None]:
        infodir = os.path.join(self.basedir, "info")
        os.makedirs(infodir)
        with open(os.path.join(infodir, "admin"), "w") as f:
            f.write("testy!")
        with open(os.path.join(infodir, "foo"), "w") as f:
            f.write("bar")
        with open(os.path.join(infodir, "environ"), "w") as f:
            f.write("something else")
        # This will not be part of worker info
        with open(os.path.join(infodir, "binary"), "wb") as f:
            f.write(b"\x90")

        # patch the log.err, otherwise trial will think something *actually*
        # failed
        self.patch(log, "err", lambda f, x: None)

        info = yield self.bot.callRemote("getWorkerInfo")

        # remove any os_ fields as they are dependent on the test environment
        info = {k: v for k, v in info.items() if not k.startswith("os_")}

        self.assertEqual(
            info,
            {
                "admin": 'testy!',
                "foo": 'bar',
                "environ": os.environ,
                "system": os.name,
                "basedir": self.basedir,
                "worker_commands": self.real_bot.remote_getCommands(),
                "version": self.real_bot.remote_getVersion(),
                "numcpus": multiprocessing.cpu_count(),
                "delete_leftover_dirs": False,
            },
        )

    def test_shutdown(self) -> defer.Deferred[Any]:
        d1: defer.Deferred[None] = defer.Deferred()
        self.patch(reactor, "stop", lambda: d1.callback(None))
        d2 = self.bot.callRemote("shutdown")
        # don't return until both the shutdown method has returned, and
        # reactor.stop has been called
        return defer.gatherResults([d1, d2], consumeErrors=True)


class FakeStep:
    "A fake master-side BuildStep that records its activities."

    def __init__(self) -> None:
        self.finished_d: defer.Deferred[None] = defer.Deferred()
        self.actions: list[list[Any]] = []

    def wait_for_finish(self) -> defer.Deferred[None]:
        return self.finished_d

    def remote_update(self, updates: Iterable[Sequence[Any]]) -> None:
        for update in updates:
            if 'elapsed' in update[0]:
                update[0]['elapsed'] = 1
        self.actions.append(["update", updates])

    def remote_complete(self, f: Any) -> None:
        self.actions.append(["complete", f])
        self.finished_d.callback(None)


class FakeBot(pb.BotPbLike):
    WorkerForBuilder = pb.WorkerForBuilderPbLike


class TestWorkerForBuilder(command.CommandTestMixin, unittest.TestCase):
    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        self.bot = FakeBot(self.basedir)
        self.bot.startService()
        self.addCleanup(self.bot.stopService)

        # get a WorkerForBuilder object from the bot and wrap it as a fake
        # remote
        builders = yield self.bot.remote_setBuilderList([('wfb', 'wfb')])
        self.wfb = FakeRemote(builders['wfb'])

        self.setUpCommand()

    def tearDown(self) -> None:
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)

    def test_print(self) -> defer.Deferred[Any]:
        return self.wfb.callRemote("print", "Hello, WorkerForBuilder.")

    def test_printWithCommand(self) -> defer.Deferred[Any]:
        self.wfb.original.command = Command(  # type: ignore[attr-defined]
            # FIXME: str passed to protocol_command?
            "builder",  # type: ignore[arg-type]
            "1",
            ["arg1", "arg2"],
        )
        return self.wfb.callRemote("print", "Hello again, WorkerForBuilder.")

    def test_setMaster(self) -> defer.Deferred[Any]:
        # not much to check here - what the WorkerForBuilder does with the
        # master is not part of the interface (and, in fact, it does very
        # little)
        return self.wfb.callRemote("setMaster", mock.Mock())

    def test_startBuild(self) -> defer.Deferred[Any]:
        return self.wfb.callRemote("startBuild")

    @defer.inlineCallbacks
    def test_startCommand(self) -> InlineCallbacksType[None]:
        # set up a fake step to receive updates
        st = FakeStep()

        # patch runprocess to handle the 'echo', below
        self.patch_runprocess(
            Expect(['echo', 'hello'], os.path.join(self.basedir, 'wfb', 'workdir'))
            .update('header', 'headers')
            .update('stdout', 'hello\n')
            .update('rc', 0)
            .exit(0)
        )

        yield self.wfb.callRemote(
            "startCommand",
            FakeRemote(st),
            "13",
            "shell",
            {"command": ['echo', 'hello'], "workdir": 'workdir'},
        )
        yield st.wait_for_finish()
        self.assertEqual(
            st.actions,
            [
                ['update', [[{'stdout': 'hello\n'}, 0]]],
                ['update', [[{'rc': 0}, 0]]],
                ['update', [[{'elapsed': 1}, 0]]],
                ['update', [[{'header': 'headers\n'}, 0]]],
                ['complete', None],
            ],
        )

    @defer.inlineCallbacks
    def test_startCommand_interruptCommand(self) -> InlineCallbacksType[None]:
        # set up a fake step to receive updates
        st = FakeStep()

        # patch runprocess to pretend to sleep (it will really just hang forever,
        # except that we interrupt it)
        self.patch_runprocess(
            Expect(['sleep', '10'], os.path.join(self.basedir, 'wfb', 'workdir'))
            .update('header', 'headers')
            .update('wait', True)
        )

        yield self.wfb.callRemote(
            "startCommand",
            FakeRemote(st),
            "13",
            "shell",
            {"command": ['sleep', '10'], "workdir": 'workdir'},
        )

        # wait a jiffy..
        d: defer.Deferred[None] = defer.Deferred()
        cast("IReactorTime", reactor).callLater(0.01, d.callback, None)
        yield d

        # and then interrupt the step
        yield self.wfb.callRemote("interruptCommand", "13", "tl/dr")

        yield st.wait_for_finish()

        self.assertEqual(
            st.actions,
            [
                ['update', [[{'rc': -1}, 0]]],
                ['update', [[{'header': 'headerskilling\n'}, 0]]],
                ['complete', None],
            ],
        )

    @defer.inlineCallbacks
    def test_startCommand_failure(self) -> InlineCallbacksType[None]:
        # set up a fake step to receive updates
        st = FakeStep()

        # patch runprocess to generate a failure
        self.patch_runprocess(
            Expect(['sleep', '10'], os.path.join(self.basedir, 'wfb', 'workdir')).exception(
                failure.Failure(Exception("Oops"))
            )
        )
        # patch the log.err, otherwise trial will think something *actually*
        # failed
        self.patch(log, "err", lambda f: None)

        yield self.wfb.callRemote(
            "startCommand",
            FakeRemote(st),
            "13",
            "shell",
            {"command": ['sleep', '10'], "workdir": 'workdir'},
        )

        yield st.wait_for_finish()

        self.assertEqual(st.actions[1][0], 'complete')
        self.assertTrue(isinstance(st.actions[1][1], failure.Failure))

    @defer.inlineCallbacks
    def test_startCommand_missing_args(self) -> InlineCallbacksType[None]:
        # set up a fake step to receive updates
        st = FakeStep()

        def do_start() -> defer.Deferred[Any]:
            return self.wfb.callRemote("startCommand", FakeRemote(st), "13", "shell", {})

        with self.assertRaises(KeyError):
            yield do_start()

    @defer.inlineCallbacks
    def test_startCommand_invalid_command(self) -> InlineCallbacksType[None]:
        # set up a fake step to receive updates
        st = FakeStep()

        def do_start() -> defer.Deferred[Any]:
            return self.wfb.callRemote("startCommand", FakeRemote(st), "13", "invalid command", {})

        with self.assertRaises(base.UnknownCommand) as e:
            yield do_start()
        self.assertEqual(
            e.exception.args,
            ("(command 13): unrecognized WorkerCommand 'invalid command'",),
        )


class TestBotFactory(unittest.TestCase):
    def setUp(self) -> None:
        self.bf = pb.BotFactory('mstr', 9010, 35, 200)

    # tests

    def test_timers(self) -> None:
        clock = self.bf._reactor = task.Clock()

        calls = []

        def callRemote(method: str) -> defer.Deferred[None]:
            calls.append(clock.seconds())
            self.assertEqual(method, 'keepalive')
            # simulate the response taking a few seconds
            d: defer.Deferred[None] = defer.Deferred()
            clock.callLater(5, d.callback, None)
            return d

        self.bf.perspective = mock.Mock()
        self.bf.perspective.callRemote = callRemote

        self.bf.startTimers()
        clock.callLater(100, self.bf.stopTimers)

        clock.pump(1 for _ in range(150))
        self.assertEqual(calls, [35, 70])

    def test_timers_exception(self) -> None:
        clock = self.bf._reactor = task.Clock()

        self.bf.perspective = mock.Mock()

        def callRemote(method: str) -> defer.Deferred[None]:
            return defer.fail(RuntimeError("oh noes"))

        self.bf.perspective.callRemote = callRemote

        self.bf.startTimers()
        clock.advance(35)
        self.assertEqual(len(self.flushLoggedErrors(RuntimeError)), 1)


# note that the Worker class is tested in test_bot_Worker
