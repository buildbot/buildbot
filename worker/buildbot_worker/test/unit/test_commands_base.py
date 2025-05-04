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

from typing import TYPE_CHECKING

from twisted.internet import defer
from twisted.trial import unittest

from buildbot_worker.commands.base import Command
from buildbot_worker.test.util.command import CommandTestMixin

if TYPE_CHECKING:
    from typing import Any

    from buildbot_worker.util.twisted import InlineCallbacksType

# set up a fake Command subclass to test the handling in Command.  Think of
# this as testing Command's subclassability.


class DummyCommand(Command):
    def setup(self, args: Any) -> None:
        self.setup_done = True
        self.interrupted = False
        self.started = False

        self.cmd_deferred: defer.Deferred[None] | None = None

    def start(self) -> defer.Deferred[None]:
        self.started = True
        data = []
        for key, value in self.args.items():
            data.append((key, value))
        self.sendStatus(data)
        self.cmd_deferred = defer.Deferred()
        return self.cmd_deferred

    def interrupt(self) -> None:
        self.interrupted = True
        self.finishCommand()

    def finishCommand(self) -> None:
        assert self.cmd_deferred is not None
        d = self.cmd_deferred
        self.cmd_deferred = None
        d.callback(None)

    def failCommand(self) -> None:
        assert self.cmd_deferred is not None
        d = self.cmd_deferred
        self.cmd_deferred = None
        d.errback(RuntimeError("forced failure"))


class DummyArgsCommand(DummyCommand):
    requiredArgs = ['workdir']


class TestDummyCommand(CommandTestMixin, unittest.TestCase):
    def setUp(self) -> None:
        self.setUpCommand()

    def assertState(
        self,
        setup_done: bool,
        running: bool,
        started: bool,
        interrupted: bool,
        msg: str | None = None,
    ) -> None:
        assert isinstance(self.cmd, DummyCommand)
        self.assertEqual(
            {
                'setup_done': self.cmd.setup_done,
                'running': self.cmd.running,
                'started': self.cmd.started,
                'interrupted': self.cmd.interrupted,
            },
            {
                'setup_done': setup_done,
                'running': running,
                'started': started,
                'interrupted': interrupted,
            },
            msg,
        )

    @defer.inlineCallbacks
    def test_run(self) -> InlineCallbacksType[None]:
        cmd = self.make_command(DummyCommand, {'stdout': 'yay'})
        self.assertState(True, False, False, False, "setup called by constructor")

        # start the command
        d = self.run_command()
        self.assertState(True, True, True, False, "started and running both set")

        # allow the command to finish and check the result
        cmd.finishCommand()

        yield d
        self.assertState(True, False, True, False, "started and not running when done")
        self.assertUpdates([('stdout', 'yay')], "updates processed")

    @defer.inlineCallbacks
    def test_run_failure(self) -> InlineCallbacksType[None]:
        cmd = self.make_command(DummyCommand, {})
        self.assertState(True, False, False, False, "setup called by constructor")

        # start the command
        d = self.run_command()
        self.assertState(True, True, True, False, "started and running both set")

        # fail the command with an exception, and check the result
        cmd.failCommand()

        with self.assertRaises(RuntimeError):
            yield d
        self.assertState(True, False, True, False, "started and not running when done")
        self.assertUpdates([], "updates processed")

    def test_run_interrupt(self) -> defer.Deferred[int]:
        cmd = self.make_command(DummyCommand, {})
        self.assertState(True, False, False, False, "setup called by constructor")

        # start the command
        d = self.run_command()
        self.assertState(True, True, True, False, "started and running both set")

        # interrupt the command
        cmd.doInterrupt()
        self.assertTrue(cmd.interrupted)

        def check(_: Any) -> None:
            self.assertState(True, False, True, True, "finishes with interrupted set")

        d.addCallback(check)
        return d

    def test_required_args(self) -> None:
        self.make_command(DummyArgsCommand, {'workdir': '.'})
        try:
            self.make_command(DummyArgsCommand, {'stdout': 'boo'})
        except ValueError:
            return
        self.fail("Command was supposed to raise ValueError when missing args")
