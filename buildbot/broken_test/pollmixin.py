# ***** BEGIN LICENSE BLOCK *****
# Version: MPL 1.1/GPL 2.0/LGPL 2.1
#
# The contents of this file are subject to the Mozilla Public License Version
# 1.1 (the "License"); you may not use this file except in compliance with
# the License. You may obtain a copy of the License at
# http://www.mozilla.org/MPL/
#
# Software distributed under the License is distributed on an "AS IS" basis,
# WITHOUT WARRANTY OF ANY KIND, either express or implied. See the License
# for the specific language governing rights and limitations under the
# License.
#
# The Original Code is Mozilla-specific Buildbot steps.
#
# The Initial Developer of the Original Code is
# Mozilla Foundation.
# Portions created by the Initial Developer are Copyright (C) 2009
# the Initial Developer. All Rights Reserved.
#
# Contributor(s):
#   Brian Warner <warner@lothar.com>
#
# Alternatively, the contents of this file may be used under the terms of
# either the GNU General Public License Version 2 or later (the "GPL"), or
# the GNU Lesser General Public License Version 2.1 or later (the "LGPL"),
# in which case the provisions of the GPL or the LGPL are applicable instead
# of those above. If you wish to allow use of your version of this file only
# under the terms of either the GPL or the LGPL, and not to allow others to
# use your version of this file under the terms of the MPL, indicate your
# decision by deleting the provisions above and replace them with the notice
# and other provisions required by the GPL or the LGPL. If you do not delete
# the provisions above, a recipient may use your version of this file under
# the terms of any one of the MPL, the GPL or the LGPL.
#
# ***** END LICENSE BLOCK *****

# copied from tahoe. I'm the original author. -Brian

import time
from twisted.internet import task

class TimeoutError(Exception):
    pass

class PollComplete(Exception):
    pass

class PollMixin:
    _poll_should_ignore_these_errors = []

    def poll(self, check_f, pollinterval=0.01, timeout=1000):
        # Return a Deferred, then call check_f periodically until it returns
        # True, at which point the Deferred will fire.. If check_f raises an
        # exception, the Deferred will errback. If the check_f does not
        # indicate success within timeout= seconds, the Deferred will
        # errback. If timeout=None, no timeout will be enforced, and the loop
        # will poll forever (or really until Trial times out).
        cutoff = None
        if timeout is not None:
            cutoff = time.time() + timeout
        lc = task.LoopingCall(self._poll, check_f, cutoff)
        d = lc.start(pollinterval)
        def _convert_done(f):
            f.trap(PollComplete)
            return None
        d.addErrback(_convert_done)
        return d

    def _poll(self, check_f, cutoff):
        if cutoff is not None and time.time() > cutoff:
            raise TimeoutError("PollMixin never saw %s return True" % check_f)
        if check_f():
            raise PollComplete()
        # since PollMixin is mostly used for unit tests, quit if we see any
        # logged errors. This should give us a nice fast failure, instead of
        # waiting for a timeout. Tests which use flushLoggedErrors() will
        # need to warn us by putting the error types they'll be ignoring in
        # self._poll_should_ignore_these_errors
        if hasattr(self, "_observer") and hasattr(self._observer, "getErrors"):
            errs = []
            for e in self._observer.getErrors():
                if not e.check(*self._poll_should_ignore_these_errors):
                    errs.append(e)
            if errs:
                print errs
                self.fail("Errors snooped, terminating early")

