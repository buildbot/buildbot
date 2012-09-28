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

from twisted.python import log
from twisted.python.procutils import which
from twisted.python import runtime

def getCommand(name):
    possibles = which(name)
    if not possibles:
        raise RuntimeError("Couldn't find executable for '%s'" % name)
    #
    # Under windows, if there is more than one executable "thing"
    # that matches (e.g. *.bat, *.cmd and *.exe), we not just use
    # the first in alphabet (*.bat/*.cmd) if there is a *.exe.
    # e.g. under MSysGit/Windows, there is both a git.cmd and a
    # git.exe on path, but we want the git.exe, since the git.cmd
    # does not seem to work properly with regard to errors raised
    # and catched in buildbot slave command (vcs.py)
    #
    if runtime.platformType  == 'win32' and len(possibles) > 1:
        possibles_exe = which(name + ".exe")
        if possibles_exe:
            return possibles_exe[0]
    return possibles[0]
