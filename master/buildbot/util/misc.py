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
from twisted.internet import defer

def deferredLocked(lock_or_attr):
    def decorator(fn):
        def wrapper(*args, **kwargs):
            lock = lock_or_attr
            if isinstance(lock, basestring):
                lock = getattr(args[0], lock)
            return lock.run(fn, *args, **kwargs)
        return wrapper
    return decorator

class SerializedInvocation(object):
    def __init__(self, method):
        self.method = method
        self.running = False
        self.pending_deferreds = []

    def __call__(self):
        d = defer.Deferred()
        self.pending_deferreds.append(d)
        if not self.running:
            self.start()
        return d

    def start(self):
        self.running = True
        invocation_deferreds = self.pending_deferreds
        self.pending_deferreds = []
        d = self.method()
        d.addErrback(log.err, 'in invocation of %r' % (self.method,))

        def notify_callers(_):
            for d in invocation_deferreds:
                d.callback(None)
        d.addCallback(notify_callers)

        def next(_):
            self.running = False
            if self.pending_deferreds:
                self.start()
            else:
                self._quiet()
        d.addBoth(next)

    def _quiet(self): # hook for tests
        pass

