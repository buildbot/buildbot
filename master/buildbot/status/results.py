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

# The first try consisted at creating a mixin with that. That attempt failed
# on method resolution issues for buildstep.
# This solution works, even if obj, is actually self, and therefore that function
# looks quite similar to a method.


def computeResultAndContinuation(obj, result, previousResult):
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

    # if we skipped this step, then don't adjust the build status
    # XXX What about putting SUCCESS < SKIPPED in the relational order
    #     in worst_status ? that would permit us to remove the if below.
    if result != SKIPPED:
        result = worst_status(previousResult, possible_overall_result)
    else:
        result = previousResult
    return result, terminate
