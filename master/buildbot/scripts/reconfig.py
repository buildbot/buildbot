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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import platform
import signal

from twisted.internet import reactor

from buildbot.scripts.logwatcher import BuildmasterTimeoutError
from buildbot.scripts.logwatcher import LogWatcher
from buildbot.scripts.logwatcher import ReconfigError
from buildbot.util import in_reactor
from buildbot.util import rewrap


class Reconfigurator:

    rc = 0

    def run(self, basedir, quiet):
        # Returns "Microsoft" for Vista and "Windows" for other versions
        if platform.system() in ("Windows", "Microsoft"):
            print("Reconfig (through SIGHUP) is not supported on Windows.")
            return

        with open(os.path.join(basedir, "twistd.pid"), "rt") as f:
            self.pid = int(f.read().strip())
        if quiet:
            os.kill(self.pid, signal.SIGHUP)
            return

        # keep reading twistd.log. Display all messages between "loading
        # configuration from ..." and "configuration update complete" or
        # "I will keep using the previous config file instead.", or until
        # 10 seconds have elapsed.

        self.sent_signal = False
        reactor.callLater(0.2, self.sighup)

        lw = LogWatcher(os.path.join(basedir, "twistd.log"))
        d = lw.start()
        d.addCallbacks(self.success, self.failure)
        d.addBoth(lambda _: self.rc)
        return d

    def sighup(self):
        if self.sent_signal:
            return
        print("sending SIGHUP to process %d" % self.pid)
        self.sent_signal = True
        os.kill(self.pid, signal.SIGHUP)

    def success(self, res):
        print("Reconfiguration appears to have completed successfully")

    def failure(self, why):
        self.rc = 1
        if why.check(BuildmasterTimeoutError):
            print("Never saw reconfiguration finish.")
        elif why.check(ReconfigError):
            print(rewrap("""\
                Reconfiguration failed. Please inspect the master.cfg file for
                errors, correct them, then try 'buildbot reconfig' again.
                """))
        elif why.check(IOError):
            # we were probably unable to open the file in the first place
            self.sighup()
        else:
            print("Error while following twistd.log: %s" % why)


@in_reactor
def reconfig(config):
    basedir = config['basedir']
    quiet = config['quiet']
    r = Reconfigurator()
    return r.run(basedir, quiet)
