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

# copy some exceptions from the DB layer
from buildbot.db.schedulers import SchedulerAlreadyClaimedError

__all__ = [
    'SchedulerAlreadyClaimedError',
    'InvalidPathError',
    'InvalidControlException',
]


class DataException(Exception):
    pass


class InvalidPathError(DataException):

    "A path argument was invalid or unknown"
    pass


class InvalidControlException(DataException):

    "Action is not supported"
    pass
