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
from future.utils import lrange

ALL_RESULTS = lrange(7)
SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY, CANCELLED = ALL_RESULTS
Results = ["success", "warnings", "failure", "skipped", "exception", "retry", "cancelled"]


def statusToString(status):
    if status is None:
        return "not finished"
    if status < 0 or status >= len(Results):
        return "Invalid status"
    return Results[status]


def worst_status(a, b):
    # SKIPPED > SUCCESS > WARNINGS > FAILURE > EXCEPTION > RETRY > CANCELLED
    # CANCELLED needs to be considered the worst.
    for s in (CANCELLED, RETRY, EXCEPTION, FAILURE, WARNINGS, SUCCESS, SKIPPED):
        if s in (a, b):
            return s


def computeResultAndTermination(obj, result, previousResult):
    possible_overall_result = result
    terminate = False
    if result == FAILURE:
        if not obj.flunkOnFailure:
            possible_overall_result = SUCCESS
        if obj.warnOnFailure:
            possible_overall_result = WARNINGS
        if obj.flunkOnFailure:
            possible_overall_result = FAILURE
        if obj.haltOnFailure:
            terminate = True
    elif result == WARNINGS:
        if not obj.warnOnWarnings:
            possible_overall_result = SUCCESS
        else:
            possible_overall_result = WARNINGS
        if obj.flunkOnWarnings:
            possible_overall_result = FAILURE
    elif result in (EXCEPTION, RETRY, CANCELLED):
        terminate = True

    result = worst_status(previousResult, possible_overall_result)
    return result, terminate


class ResultComputingConfigMixin(object):

    haltOnFailure = False
    flunkOnWarnings = False
    flunkOnFailure = True
    warnOnWarnings = False
    warnOnFailure = False

    resultConfig = [
        "haltOnFailure",
        "flunkOnWarnings",
        "flunkOnFailure",
        "warnOnWarnings",
        "warnOnFailure",
    ]
