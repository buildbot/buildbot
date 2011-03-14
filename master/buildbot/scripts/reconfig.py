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


import os, signal, platform
from twisted.internet import reactor

from buildbot.scripts.logwatcher import LogWatcher, BuildmasterTimeoutError, \
     ReconfigError

class Reconfigurator:
    def run(self, config):
        # Returns "Microsoft" for Vista and "Windows" for other versions
        if platform.system() in ("Windows", "Microsoft"):
            print "Reconfig (through SIGHUP) is not supported on Windows."
            print "The 'buildbot debugclient' tool can trigger a reconfig"
            print "remotely, but requires Gtk+ libraries to run."
            return

        basedir = config['basedir']
        quiet = config['quiet']
        os.chdir(basedir)
        f = open("twistd.pid", "rt")
        self.pid = int(f.read().strip())
        if quiet:
            os.kill(self.pid, signal.SIGHUP)
            return

        # keep reading twistd.log. Display all messages between "loading
        # configuration from ..." and "configuration update complete" or
        # "I will keep using the previous config file instead.", or until
        # 10 seconds have elapsed.

        self.sent_signal = False
        lw = LogWatcher("twistd.log")
        d = lw.start()
        d.addCallbacks(self.success, self.failure)
        reactor.callLater(0.2, self.sighup)
        reactor.run()

    def sighup(self):
        if self.sent_signal:
            return
        print "sending SIGHUP to process %d" % self.pid
        self.sent_signal = True
        os.kill(self.pid, signal.SIGHUP)

    def success(self, res):
        print """
Reconfiguration appears to have completed successfully.
"""
        reactor.stop()

    def failure(self, why):
        if why.check(BuildmasterTimeoutError):
            print "Never saw reconfiguration finish."
        elif why.check(ReconfigError):
            print """
Reconfiguration failed. Please inspect the master.cfg file for errors,
correct them, then try 'buildbot reconfig' again.
"""
        elif why.check(IOError):
            # we were probably unable to open the file in the first place
            self.sighup()
        else:
            print "Error while following twistd.log: %s" % why
        reactor.stop()

def reconfig(config):
    r = Reconfigurator()
    r.run(config)

