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

from __future__ import with_statement


import os
import signal
import platform
from twisted.internet import reactor

from buildbot.scripts.logwatcher import LogWatcher, BuildmasterTimeoutError, \
     CleanShutdownError
from buildbot.util import in_reactor
from buildbot.scripts import base

class CleanShutdown:

    rc = 0

    def run(self, basedir, quiet):

        if not base.isBuildmasterDir(basedir):
           print "not a buildmaster directory"
           return 1

        if os.path.exists(os.path.join(basedir, "twistd.pid")):
           with open(os.path.join(basedir, "twistd.pid"), "rt") as f:
                self.pid = int(f.read().strip())
           if quiet:
               os.kill(self.pid, signal.SIGUSR1)
               return
        else:
           print "not running"
           return 0

        # keep reading twistd.log. Display all messages between "loading
        # configuration from ..." and "configuration update complete" or
        # "I will keep using the previous config file instead.", or until
        # 10 seconds have elapsed.

        self.sent_signal = False
        reactor.callLater(0.2, self.sigusr1)

        lw = LogWatcher(os.path.join(basedir, "twistd.log"))
        d = lw.start()
        d.addCallbacks(self.success, self.failure)
        d.addBoth(lambda _ : self.rc)
        return d

    def sigusr1(self):
        if self.sent_signal:
            return
        print "sending SIGUSR1 to process %d" % self.pid
        self.sent_signal = True
        os.kill(self.pid, signal.SIGUSR1)

    def success(self, res):
        print """
Clean shutdown appears to have completed successfully.
"""

    def failure(self, why):
        self.rc = 1
        if why.check(CleanShutdownError):
            print """
Clean Shutdown failed. 
"""
        else:
            print "Error while following twistd.log: %s" % why

@in_reactor
def clean(config):
    basedir = config['basedir']
    quiet = config['quiet']
    r = CleanShutdown()
    return r.run(basedir, quiet)
