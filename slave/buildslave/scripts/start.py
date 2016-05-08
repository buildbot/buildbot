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

import os
import sys
import time

from twisted.python import log

from buildslave.scripts import base


class Follower(object):

    def follow(self):
        from twisted.internet import reactor
        from buildslave.scripts.logwatcher import LogWatcher
        self.rc = 0
        log.msg("Following twistd.log until startup finished..")
        lw = LogWatcher("twistd.log")
        d = lw.start()
        d.addCallbacks(self._success, self._failure)
        reactor.run()
        return self.rc

    def _success(self, processtype):
        from twisted.internet import reactor
        log.msg("The %s appears to have (re)started correctly." % processtype)
        self.rc = 0
        reactor.stop()

    def _failure(self, why):
        from twisted.internet import reactor
        from buildslave.scripts.logwatcher import BuildmasterTimeoutError, \
            ReconfigError, BuildslaveTimeoutError, BuildSlaveDetectedError
        if why.check(BuildmasterTimeoutError):
            log.msg("""
The buildslave took more than 10 seconds to start, so we were unable to
confirm that it started correctly. Please 'tail twistd.log' and look for a
line that says 'configuration update complete' to verify correct startup.
""")
        elif why.check(BuildslaveTimeoutError):
            log.msg("""
The buildslave took more than 10 seconds to start and/or connect to the
buildslave, so we were unable to confirm that it started and connected
correctly. Please 'tail twistd.log' and look for a line that says 'message
from master: attached' to verify correct startup. If you see a bunch of
messages like 'will retry in 6 seconds', your buildslave might not have the
correct hostname or portnumber for the buildslave, or the buildslave might
not be running. If you see messages like
   'Failure: twisted.cred.error.UnauthorizedLogin'
then your buildslave might be using the wrong botname or password. Please
correct these problems and then restart the buildslave.
""")
        elif why.check(ReconfigError):
            log.msg("""
The buildslave appears to have encountered an error in the master.cfg config
file during startup. It is probably running with an empty configuration right
now. Please inspect and fix master.cfg, then restart the buildslave.
""")
        elif why.check(BuildSlaveDetectedError):
            log.msg("""
Buildslave is starting up, not following logfile.
""")
        else:
            log.msg("""
Unable to confirm that the buildslave started correctly. You may need to
stop it, fix the config file, and restart.
""")
            log.msg(why)
        self.rc = 1
        reactor.stop()


def startCommand(config):
    basedir = config['basedir']
    if not base.isBuildslaveDir(basedir):
        return 1

    return startSlave(basedir, config['quiet'], config['nodaemon'])


def startSlave(basedir, quiet, nodaemon):
    """
    Start slave process.

    Fork and start twisted application described in basedir buildbot.tac file.
    Print it's log messages to stdout for a while and try to figure out if
    start was successful.

    If quiet or nodaemon parameters are True, or we are running on a win32
    system, will not fork and log will not be printed to stdout.

    @param  basedir: buildslave's basedir path
    @param    quiet: don't display startup log messages
    @param nodaemon: don't daemonize (stay in foreground)
    @return: 0 if slave was successfully started,
             1 if we are not sure that slave started successfully
    """

    os.chdir(basedir)
    if quiet or nodaemon:
        return launch(nodaemon)

    # we probably can't do this os.fork under windows
    from twisted.python.runtime import platformType
    if platformType == "win32":
        return launch(nodaemon)

    # fork a child to launch the daemon, while the parent process tails the
    # logfile
    if os.fork():
        # this is the parent
        rc = Follower().follow()
        return rc
    # this is the child: give the logfile-watching parent a chance to start
    # watching it before we start the daemon
    time.sleep(0.2)
    launch(nodaemon)


def launch(nodaemon):
    sys.path.insert(0, os.path.abspath(os.getcwd()))

    # see if we can launch the application without actually having to
    # spawn twistd, since spawning processes correctly is a real hassle
    # on windows.
    from twisted.python.runtime import platformType
    argv = ["twistd",
            "--no_save",
            "--logfile=twistd.log",  # windows doesn't use the same default
            "--python=buildbot.tac"]
    if nodaemon:
        argv.extend(['--nodaemon'])
    sys.argv = argv

    # this is copied from bin/twistd. twisted-2.0.0 through 2.4.0 use
    # _twistw.run . Twisted-2.5.0 and later use twistd.run, even for
    # windows.
    from twisted import __version__
    major, minor, ignored = __version__.split(".", 2)
    major = int(major)
    minor = int(minor)
    if (platformType == "win32" and (major == 2 and minor < 5)):
        from twisted.scripts import _twistw
        run = _twistw.run
    else:
        from twisted.scripts import twistd
        run = twistd.run
    run()
