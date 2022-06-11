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

from twisted.internet import defer


class FakeConnection:

    is_fake_test_connection = True

    _waiting_for_interrupt = False

    def __init__(self, testcase, name, step, commands_numbers_to_interrupt):
        self.testcase = testcase
        self.name = name
        self.step = step
        self._commands_numbers_to_interrupt = commands_numbers_to_interrupt
        self._block_on_interrupt = False
        self._next_command_number = 0
        self._blocked_deferreds = []

    @defer.inlineCallbacks
    def remoteStartCommand(self, remote_command, builder_name, command_id, command_name, args):

        self._waiting_for_interrupt = False
        if self._next_command_number in self._commands_numbers_to_interrupt:
            self._waiting_for_interrupt = True

            yield self.step.interrupt('interrupt reason')

            if self._waiting_for_interrupt:
                raise RuntimeError("Interrupted step, but command was not interrupted")

        self._next_command_number += 1
        yield self.testcase._connection_remote_start_command(remote_command, self, builder_name)

        # running behaviors may still attempt interrupt the command
        if self._waiting_for_interrupt:
            raise RuntimeError("Interrupted step, but command was not interrupted")

    def remoteInterruptCommand(self, builder_name, command_id, why):
        if not self._waiting_for_interrupt:
            raise RuntimeError("Got interrupt, but FakeConnection was not expecting it")
        self._waiting_for_interrupt = False

        if self._block_on_interrupt:
            d = defer.Deferred()
            self._blocked_deferreds.append(d)
            return d
        else:
            return defer.succeed(None)

    def set_expect_interrupt(self):
        if self._waiting_for_interrupt:
            raise RuntimeError("Already expecting interrupt but got additional request")
        self._waiting_for_interrupt = True

    def set_block_on_interrupt(self):
        self._block_on_interrupt = True

    def unblock_waiters(self):
        for d in self._blocked_deferreds:
            d.callback(None)
