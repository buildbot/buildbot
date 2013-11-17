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

from twisted.python import failure
from twisted.trial import unittest


def patch():
    """
    Patch in successResultOf, failureResultOf and assertNoResult for versions
    of twisted that don't support them.

    (used for testing only)
    """
    unittest.TestCase.successResultOf = successResultOf
    unittest.TestCase.failureResultOf = failureResultOf
    unittest.TestCase.assertNoResult = assertNoResult

#
# Everything below this line was taken from Twisted, except as annotated.  See
# https://twistedmatrix.com/trac/browser/trunk/twisted/trial/_synctest.py?rev=37834#L594
#
#    Merge failureResultOf-optional-types-6380: expected types of failureResultOf
#
#    Author: cyli
#    Reviewer: tom.prince
# Fixes: #6380
#
#    Allow failureResultOf to take optional expected failure types, so that if an unexpected failure occurs, the failureResultOf assertion will fail.


def successResultOf(self, deferred):
    """
    Return the current success result of C{deferred} or raise
    C{self.failException}.

    @param deferred: A L{Deferred<twisted.internet.defer.Deferred>} which
        has a success result.  This means
        L{Deferred.callback<twisted.internet.defer.Deferred.callback>} or
        L{Deferred.errback<twisted.internet.defer.Deferred.errback>} has
        been called on it and it has reached the end of its callback chain
        and the last callback or errback returned a non-L{failure.Failure}.
    @type deferred: L{Deferred<twisted.internet.defer.Deferred>}

    @raise SynchronousTestCase.failureException: If the
        L{Deferred<twisted.internet.defer.Deferred>} has no result or has a
        failure result.

    @return: The result of C{deferred}.
    """
    result = []
    deferred.addBoth(result.append)
    if not result:
        self.fail(
            "Success result expected on %r, found no result instead" % (
                deferred,))
    elif isinstance(result[0], failure.Failure):
        self.fail(
            "Success result expected on %r, "
            "found failure result instead:\n%s" % (
                deferred, result[0].getTraceback()))
    else:
        return result[0]


def failureResultOf(self, deferred, *expectedExceptionTypes):
    """
    Return the current failure result of C{deferred} or raise
    C{self.failException}.

    @param deferred: A L{Deferred<twisted.internet.defer.Deferred>} which
        has a failure result.  This means
        L{Deferred.callback<twisted.internet.defer.Deferred.callback>} or
        L{Deferred.errback<twisted.internet.defer.Deferred.errback>} has
        been called on it and it has reached the end of its callback chain
        and the last callback or errback raised an exception or returned a
        L{failure.Failure}.
    @type deferred: L{Deferred<twisted.internet.defer.Deferred>}

    @param expectedExceptionTypes: Exception types to expect - if
        provided, and the the exception wrapped by the failure result is
        not one of the types provided, then this test will fail.

    @raise SynchronousTestCase.failureException: If the
        L{Deferred<twisted.internet.defer.Deferred>} has no result, has a
        success result, or has an unexpected failure result.

    @return: The failure result of C{deferred}.
    @rtype: L{failure.Failure}
    """
    result = []
    deferred.addBoth(result.append)
    if not result:
        self.fail(
            "Failure result expected on %r, found no result instead" % (
                deferred,))
    elif not isinstance(result[0], failure.Failure):
        self.fail(
            "Failure result expected on %r, "
            "found success result (%r) instead" % (deferred, result[0]))
    elif (expectedExceptionTypes and
          not result[0].check(*expectedExceptionTypes)):
        expectedString = " or ".join([
            '.'.join((t.__module__, t.__name__)) for t in
            expectedExceptionTypes])

        self.fail(
            "Failure of type (%s) expected on %r, "
            "found type %r instead: %s" % (
                expectedString, deferred, result[0].type,
                result[0].getTraceback()))
    else:
        return result[0]


def assertNoResult(self, deferred):
    """
    Assert that C{deferred} does not have a result at this point.

    If the assertion succeeds, then the result of C{deferred} is left
    unchanged. Otherwise, any L{failure.Failure} result is swallowed.

    @param deferred: A L{Deferred<twisted.internet.defer.Deferred>} without
        a result.  This means that neither
        L{Deferred.callback<twisted.internet.defer.Deferred.callback>} nor
        L{Deferred.errback<twisted.internet.defer.Deferred.errback>} has
        been called, or that the
        L{Deferred<twisted.internet.defer.Deferred>} is waiting on another
        L{Deferred<twisted.internet.defer.Deferred>} for a result.
    @type deferred: L{Deferred<twisted.internet.defer.Deferred>}

    @raise SynchronousTestCase.failureException: If the
        L{Deferred<twisted.internet.defer.Deferred>} has a result.
    """
    result = []

    def cb(res):
        result.append(res)
        return res
    deferred.addBoth(cb)
    if result:
        # If there is already a failure, the self.fail below will
        # report it, so swallow it in the deferred
        deferred.addErrback(lambda _: None)
        self.fail(
            "No result expected on %r, found %r instead" % (
                deferred, result[0]))
