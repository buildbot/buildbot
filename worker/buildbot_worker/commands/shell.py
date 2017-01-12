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

import os

from buildbot_worker import runprocess
from buildbot_worker.commands import base


class WorkerShellCommand(base.Command):

    requiredArgs = ['workdir', 'command']

    def start(self):
        args = self.args
        workdir = os.path.join(self.builder.basedir, args['workdir'])

        c = runprocess.RunProcess(
            self.builder,
            args['command'],
            workdir,
            environ=args.get('env'),
            timeout=args.get('timeout', None),
            maxTime=args.get('maxTime', None),
            sigtermTime=args.get('sigtermTime', None),
            sendStdout=args.get('want_stdout', True),
            sendStderr=args.get('want_stderr', True),
            sendRC=True,
            initialStdin=args.get('initial_stdin'),
            logfiles=args.get('logfiles', {}),
            usePTY=args.get('usePTY', False),
            logEnviron=args.get('logEnviron', True),
        )
        if args.get('interruptSignal'):
            c.interruptSignal = args['interruptSignal']
        c._reactor = self._reactor
        self.command = c
        d = self.command.start()
        return d

    def interrupt(self):
        self.interrupted = True
        self.command.kill("command interrupted")

    def writeStdin(self, data):
        self.command.writeStdin(data)

    def closeStdin(self):
        self.command.closeStdin()
