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
"""
Miscellaneous utilities; these should be imported from C{buildbot.util}, not
directly from this module.
"""

from __future__ import absolute_import
from __future__ import print_function
from future.utils import string_types

from twisted.internet import reactor


def deferredLocked(lock_or_attr):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            lock = lock_or_attr
            if isinstance(lock, string_types):
                lock = getattr(args[0], lock)
            return lock.run(fn, *args, **kwargs)
        return wrapper
    return decorator


def cancelAfter(seconds, deferred, _reactor=reactor):
    delayedCall = _reactor.callLater(seconds, deferred.cancel)

    # cancel the delayedCall when the underlying deferred fires
    @deferred.addBoth
    def cancelTimer(x):
        if delayedCall.active():
            delayedCall.cancel()
        return x

    return deferred
