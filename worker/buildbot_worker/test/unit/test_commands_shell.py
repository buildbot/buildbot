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

from twisted.trial import unittest

from buildbot_worker.commands import shell
from buildbot_worker.test.fake.runprocess import Expect
from buildbot_worker.test.util.command import CommandTestMixin


class TestWorkerShellCommand(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.make_command(shell.WorkerShellCommand, dict(
            command=['echo', 'hello'],
            workdir='workdir',
        ))

        self.patch_runprocess(
            Expect(['echo', 'hello'], self.basedir_workdir)
            + {'hdr': 'headers'} + {'stdout': 'hello\n'} + {'rc': 0}
            + 0,
        )

        d = self.run_command()

        # note that WorkerShellCommand does not add any extra updates of it own
        def check(_):
            self.assertUpdates(
                [{'hdr': 'headers'}, {'stdout': 'hello\n'}, {'rc': 0}],
                self.builder.show())
        d.addCallback(check)
        return d

    # TODO: test all functionality that WorkerShellCommand adds atop RunProcess
