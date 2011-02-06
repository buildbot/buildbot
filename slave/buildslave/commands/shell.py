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

import os

from buildslave.commands import base
from buildslave import runprocess

class SlaveShellCommand(base.Command):
    """This is a Command which runs a shell command. The args dict contains
    the following keys:

        - ['command'] (required): a shell command to run. If this is a string,
                                  it will be run with /bin/sh (['/bin/sh',
                                  '-c', command]). If it is a list
                                  (preferred), it will be used directly.
        - ['workdir'] (required): subdirectory in which the command will be
                                  run, relative to the builder dir
        - ['env']: a dict of environment variables to augment/replace
                   os.environ . PYTHONPATH is treated specially, and
                   should be a list of path components to be prepended to
                   any existing PYTHONPATH environment variable.
        - ['initial_stdin']: a string which will be written to the command's
                             stdin as soon as it starts
        - ['want_stdout']: 0 if stdout should be thrown away
        - ['want_stderr']: 0 if stderr should be thrown away
        - ['usePTY']: True or False if the command should use a PTY (defaults to
                      configuration of the slave)
        - ['not_really']: 1 to skip execution and return rc=0
        - ['timeout']: seconds of silence to tolerate before killing command
        - ['maxTime']: seconds before killing command
        - ['logfiles']: dict mapping LogFile name to the workdir-relative
                        filename of a local log file. This local file will be
                        watched just like 'tail -f', and all changes will be
                        written to 'log' status updates.
        - ['logEnviron']: False to not log the environment variables on the slave

    ShellCommand creates the following status messages:
        - {'stdout': data} : when stdout data is available
        - {'stderr': data} : when stderr data is available
        - {'header': data} : when headers (command start/stop) are available
        - {'log': (logfile_name, data)} : when log files have new contents
        - {'rc': rc} : when the process has terminated
    """

    def start(self):
        args = self.args
        # args['workdir'] is relative to Builder directory, and is required.
        assert args['workdir'] is not None
        workdir = os.path.join(self.builder.basedir, args['workdir'])

        c = runprocess.RunProcess(
                         self.builder,
                         args['command'],
                         workdir,
                         environ=args.get('env'),
                         timeout=args.get('timeout', None),
                         maxTime=args.get('maxTime', None),
                         sendStdout=args.get('want_stdout', True),
                         sendStderr=args.get('want_stderr', True),
                         sendRC=True,
                         initialStdin=args.get('initial_stdin'),
                         logfiles=args.get('logfiles', {}),
                         usePTY=args.get('usePTY', "slave-config"),
                         logEnviron=args.get('logEnviron', True),
                         )
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
