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

def deferredLocked(lock_or_attr):
    """
    Wrap a function which returns a Deferred with a DeferredLock.  The
    DeferredLock is given by the argument to the decorator; if this argument is
    a string, then the function is assumed to be a method, and the named
    attribute of SELF is used as the lock object.
    """
    def decorator(fn):
        def wrapper(*args, **kwargs):
            lock = lock_or_attr
            if isinstance(lock, basestring):
                lock = getattr(args[0], lock)
            d = lock.acquire()
            d.addCallback(lambda _ : fn(*args, **kwargs))
            def release(val):
                lock.release()
                return val
            d.addBoth(release)
            return d
        return wrapper
    return decorator

