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

SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY, CANCELLED = range(7)
Results = ["success", "warnings", "failure", "skipped", "exception", "retry", "cancelled"]


def worst_status(a, b):
    # SUCCESS > WARNINGS > FAILURE > EXCEPTION > RETRY > CANCELLED
    # CANCELLED needs to be considered the worst.
    for s in (CANCELLED, RETRY, EXCEPTION, FAILURE, WARNINGS, SKIPPED, SUCCESS):
        if s in (a, b):
            return s


def reduceResults(resList):
    return reduce(worst_status, resList, SUCCESS)
