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
import sys

from twisted.internet import protocol
from twisted.internet import reactor
from twisted.python.runtime import platformType

from buildbot.scripts import base
from buildbot.scripts.logwatcher import BuildmasterStartupError
from buildbot.scripts.logwatcher import BuildmasterTimeoutError
from buildbot.scripts.logwatcher import LogWatcher
from buildbot.scripts.logwatcher import ReconfigError
from buildbot.util import rewrap


class Follower:

    def follow(self, basedir):
        self.rc = 0
        print("Following twistd.log until startup finished..")
        lw = LogWatcher(os.path.join(basedir, "twistd.log"))
        d = lw.start()
        d.addCallbacks(self._success, self._failure)
        reactor.run()
        return self.rc

    def _success(self, _):
        print("The buildmaster appears to have (re)started correctly.")
        self.rc = 0
        reactor.stop()

    def _failure(self, why):
        if why.check(BuildmasterTimeoutError):
            print(rewrap("""\
                The buildmaster took more than 10 seconds to start, so we were
                unable to confirm that it started correctly.
                Please 'tail twistd.log' and look for a line that says
                'BuildMaster is running' to verify correct startup.
                """))
        elif why.check(ReconfigError):
            print(rewrap("""\
                The buildmaster appears to have encountered an error in the
                master.cfg config file during startup.
                Please inspect and fix master.cfg, then restart the
                buildmaster.
                """))
        elif why.check(BuildmasterStartupError):
            print(rewrap("""\
                The buildmaster startup failed. Please see 'twistd.log' for
                possible reason.
                """))
        else:
            print(rewrap("""\
                Unable to confirm that the buildmaster started correctly.
                You may need to stop it, fix the config file, and restart.
                """))
            print(why)
        self.rc = 1
        reactor.stop()


def launchNoDaemon(config):
    os.chdir(config['basedir'])
    sys.path.insert(0, os.path.abspath(config['basedir']))

    argv = ["twistd",
            "--no_save",
            '--nodaemon',
            "--logfile=twistd.log",  # windows doesn't use the same default
            "--python=buildbot.tac"]
    sys.argv = argv

    # this is copied from bin/twistd. twisted-2.0.0 through 2.4.0 use
    # _twistw.run . Twisted-2.5.0 and later use twistd.run, even for
    # windows.
    from twisted.scripts import twistd
    twistd.run()


def launch(config):
    os.chdir(config['basedir'])
    sys.path.insert(0, os.path.abspath(config['basedir']))

    # see if we can launch the application without actually having to
    # spawn twistd, since spawning processes correctly is a real hassle
    # on windows.
    argv = [sys.executable,
            "-c",
            # this is copied from bin/twistd. twisted-2.0.0 through 2.4.0 use
            # _twistw.run . Twisted-2.5.0 and later use twistd.run, even for
            # windows.
            "from twisted.scripts import twistd; twistd.run()",
            "--no_save",
            "--logfile=twistd.log",  # windows doesn't use the same default
            "--python=buildbot.tac"]

    # ProcessProtocol just ignores all output
    proc = reactor.spawnProcess(
        protocol.ProcessProtocol(), sys.executable, argv, env=os.environ)

    if platformType == "win32":
        with open("twistd.pid", "w") as pidfile:
            pidfile.write("{0}".format(proc.pid))


def start(config):
    if not base.isBuildmasterDir(config['basedir']):
        return 1

    if config['nodaemon']:
        launchNoDaemon(config)
        return 0

    launch(config)

    # We don't have tail on windows
    if platformType == "win32" or config['quiet']:
        return 0

    # this is the parent
    rc = Follower().follow(config['basedir'])
    return rc
