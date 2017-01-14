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


class AbandonChain(Exception):

    """A series of chained steps can raise this exception to indicate that
    one of the intermediate RunProcesses has failed, such that there is no
    point in running the remainder. 'rc' should be the non-zero exit code of
    the failing ShellCommand."""

    def __repr__(self):
        return "<AbandonChain rc=%s>" % self.args[0]
