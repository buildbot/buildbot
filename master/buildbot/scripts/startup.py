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


import os, sys, time

class Follower:
    def follow(self):
        from twisted.internet import reactor
        from buildbot.scripts.logwatcher import LogWatcher
        self.rc = 0
        print "Following twistd.log until startup finished.."
        lw = LogWatcher("twistd.log")
        d = lw.start()
        d.addCallbacks(self._success, self._failure)
        reactor.run()
        return self.rc

    def _success(self, _):
        from twisted.internet import reactor
        print "The buildmaster appears to have (re)started correctly."
        self.rc = 0
        reactor.stop()

    def _failure(self, why):
        from twisted.internet import reactor
        from buildbot.scripts.logwatcher import BuildmasterTimeoutError
        from buildbot.scripts.logwatcher import ReconfigError
        if why.check(BuildmasterTimeoutError):
            print """
The buildmaster took more than 10 seconds to start, so we were unable to
confirm that it started correctly. Please 'tail twistd.log' and look for a
line that says 'configuration update complete' to verify correct startup.
"""
        elif why.check(ReconfigError):
            print """
The buildmaster appears to have encountered an error in the master.cfg config
file during startup. Please inspect and fix master.cfg, then restart the
buildmaster.
"""
        else:
            print """
Unable to confirm that the buildmaster started correctly. You may need to
stop it, fix the config file, and restart.
"""
            print why
        self.rc = 1
        reactor.stop()


def start(config):
    os.chdir(config['basedir'])
    if not os.path.exists("buildbot.tac"):
        print "This doesn't look like a buildbot base directory:"
        print "No buildbot.tac file."
        print "Giving up!"
        sys.exit(1)
    if config['quiet']:
        return launch(config)

    # we probably can't do this os.fork under windows
    from twisted.python.runtime import platformType
    if platformType == "win32":
        return launch(config)

    # fork a child to launch the daemon, while the parent process tails the
    # logfile
    if os.fork():
        # this is the parent
        rc = Follower().follow()
        sys.exit(rc)
    # this is the child: give the logfile-watching parent a chance to start
    # watching it before we start the daemon
    time.sleep(0.2)
    launch(config)

def launch(config):
    sys.path.insert(0, os.path.abspath(os.getcwd()))

    # see if we can launch the application without actually having to
    # spawn twistd, since spawning processes correctly is a real hassle
    # on windows.
    argv = ["twistd",
            "--no_save",
            "--logfile=twistd.log", # windows doesn't use the same default
            "--python=buildbot.tac"]
    sys.argv = argv

    # this is copied from bin/twistd. twisted-2.0.0 through 2.4.0 use
    # _twistw.run . Twisted-2.5.0 and later use twistd.run, even for
    # windows.
    from twisted.scripts import twistd
    twistd.run()

