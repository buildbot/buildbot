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

from twisted.internet import defer

def patch():
    """
    Patch gatherResults to support consumeErrors on old versions of twisted
    """
    defer.gatherResults = gatherResults

#############################################################################
# Everything below this line was taken from Twisted, except as annotated.  See
# https://twistedmatrix.com/trac/browser/trunk/twisted/internet/defer.py?rev=32405#L805
#
#    Merge gatherresults-consumeerrors-5159
#
#    Author: dustin
#    Reviewer: exarkun
#    Fixes: #5159
#
#    Add a `consumeErrors` parameter to `twisted.internet.defer.gatherResults`
#    with the same meaning as the parameter of the same name accepted by
#    `DeferredList`.



def _parseDListResult(l, fireOnOneErrback=False):
    if __debug__:
        for success, value in l:
            assert success
    return [x[1] for x in l]

def gatherResults(deferredList, consumeErrors=False):
    """
    Returns, via a L{Deferred}, a list with the results of the given
    L{Deferred}s - in effect, a "join" of multiple deferred operations.

    The returned L{Deferred} will fire when I{all} of the provided L{Deferred}s
    have fired, or when any one of them has failed.

    This differs from L{DeferredList} in that you don't need to parse
    the result for success/failure.

    @type deferredList:  C{list} of L{Deferred}s

    @param consumeErrors: (keyword param) a flag, defaulting to False,
        indicating that failures in any of the given L{Deferreds} should not be
        propagated to errbacks added to the individual L{Deferreds} after this
        L{gatherResults} invocation.  Any such errors in the individual
        L{Deferred}s will be converted to a callback result of C{None}.  This
        is useful to prevent spurious 'Unhandled error in Deferred' messages
        from being logged.  This parameter is available since 11.1.0.
    @type consumeErrors: C{bool}
    """
    d = defer.DeferredList(deferredList, fireOnOneErrback=True,
                                   consumeErrors=consumeErrors)
    d.addCallback(_parseDListResult)
    return d
