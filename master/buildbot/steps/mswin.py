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

from twisted.python import log

from buildbot.process.results import EXCEPTION
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.process.results import WARNINGS
from buildbot.steps.shell import ShellCommand


class Robocopy(ShellCommand):

    """ Robocopy build step.

    This is just a wrapper around the standard shell command that
    will handle arguments and return codes accordingly for Robocopy.
    """
    renderables = [
        'custom_opts',
        'destination',
        'exclude_dirs',
        'exclude_files',
        'files',
        'source'
    ]

    # Robocopy exit flags (they are combined to make up the exit code)
    # See: http://ss64.com/nt/robocopy-exit.html
    return_flags = {
        FAILURE: [8, 16],
        WARNINGS: [2, 4],
        SUCCESS: [0, 1]
    }

    def __init__(self, source, destination,
                 exclude=None,
                 exclude_files=None,
                 **kwargs):
        self.source = source
        self.destination = destination

        self.files = kwargs.pop('files', None)
        self.recursive = kwargs.pop('recursive', False)
        self.mirror = kwargs.pop('mirror', False)
        self.move = kwargs.pop('move', False)

        self.exclude_files = exclude_files
        if exclude and not exclude_files:
            self.exclude_files = exclude

        self.exclude_dirs = kwargs.pop('exclude_dirs', None)
        self.custom_opts = kwargs.pop('custom_opts', None)
        self.verbose = kwargs.pop('verbose', False)

        ShellCommand.__init__(self, **kwargs)

    def start(self):
        command = ['robocopy', self.source, self.destination]
        if self.files:
            command += self.files
        if self.recursive:
            command.append('/E')
        if self.mirror:
            command.append('/MIR')
        if self.move:
            command.append('/MOVE')
        if self.exclude_files:
            command.append('/XF')
            command += self.exclude_files
        if self.exclude_dirs:
            command.append('/XD')
            command += self.exclude_dirs
        if self.verbose:
            command += ['/V', '/TS', '/FP']
        if self.custom_opts:
            command += self.custom_opts
        command += ['/TEE', '/NP']
        self.setCommand(command)
        ShellCommand.start(self)

    def evaluateCommand(self, cmd):
        # If we have a "clean" return code, it's good.
        # Otherwise, look for errors first, warnings second.
        if cmd.rc == 0 or cmd.rc == 1:
            return SUCCESS
        for result in [FAILURE, WARNINGS]:
            for flag in self.return_flags[result]:
                if (cmd.rc & flag) == flag:
                    return result

        log.msg("Unknown return code for Robocopy: %s" % cmd.rc)
        return EXCEPTION
