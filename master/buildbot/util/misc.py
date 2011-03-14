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

from twisted.python import log

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

class SerializedInvocation(object):
    """
    A method wrapper to serialize calls to a deferred method.  If a second call
    occurs while the first call is still executing, it will not begin until the
    first call has finished.  If multiple calls queue up, they will be
    collapsed into a single call.

    The effect is that the underlying method is guaranteed to be called at
    least once after every call to the wrapper.

    Note that this cannot be used as a decorator on a method, as it will
    serialize invocations across all class instances.  Also note that while the
    underlying method must return a Deferred, the resulting wrapper does not.
    Tests can monkey-patch the C{_quiet} method to be notified when all planned
    invocations are complete.
    """
    def __init__(self, method):
        self.method = method
        self.running = False
        self.need_run = False

    def __call__(self):
        self.need_run = True
        if self.running:
            return

        # not running, so start a run
        self.run_method()

    def run_method(self):
        self.running = True
        self.need_run = False
        d = self.method()
        d.addErrback(log.err)
        def update_state(x):
            self.running = False
            if self.need_run:
                self.run_method()
            else:
                self._quiet()
        d.addBoth(update_state)

    def _quiet(self): # hook for tests
        pass

