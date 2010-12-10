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

import threading
import time

from twisted.python import log

class ThreadLeakMixin(object):
    """
    Monitor for leaking thread pools. Just call the setUp and tearDown methods!
    """
    def setUpThreadLeak(self):
        self.start_thdcount = len(threading.enumerate())

    def tearDownThreadLeak(self):
        # double-check we haven't left a ThreadPool open.  Sometimes, threads
        # take a while to go away, so this will wait up to 5s for that to occur
        for _ in xrange(5):
            cur_thdcount = len(threading.enumerate())
            if cur_thdcount - self.start_thdcount < 1:
                return
            log.msg("threadcount: %d (start) %d (now)" % (self.start_thdcount, cur_thdcount))
            time.sleep(1)
        self.fail("leaked %d threads" % (cur_thdcount - self.start_thdcount))
