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

from twisted.python import log

from buildbot.steps.shell import ShellCommand
from buildbot.status.results import SUCCESS, WARNINGS, FAILURE, EXCEPTION


class Robocopy(ShellCommand):
    """ Robocopy build step.

    This is just a wrapper around the standard shell command that
    will handle arguments and return codes accordingly for Robocopy.
    """
    renderables = ['source', 'destination', 'files', 'exclude']

    # Robocopy exit flags (they are combined to make up the exit code)
    # See: http://ss64.com/nt/robocopy-exit.html
    return_flags = {
                FAILURE: [8, 16],
                WARNINGS: [2, 4],
                SUCCESS: [0, 1]
            }

    def __init__(self, source, destination,
        files=None,
        recursive=False,
        mirror=False,
        move=False,
        exclude=None,
        verbose=False,
        **kwargs):
        self.source = source
        self.destination = destination
        self.files = files
        self.recursive = recursive
        self.mirror = mirror
        self.move = move
        self.exclude = exclude
        self.verbose = verbose
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
        if self.exclude:
            command.append('/XF')
            command += self.exclude
        if self.verbose:
            command.append('/V /TS /FP')
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
