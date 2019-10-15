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
import textwrap

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

    def follow(self, basedir, timeout=None):
        self.rc = 0
        self._timeout = timeout if timeout else 10.0
        print("Following twistd.log until startup finished..")
        lw = LogWatcher(os.path.join(basedir, "twistd.log"),
                        timeout=self._timeout)
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
                The buildmaster took more than {0} seconds to start, so we were
                unable to confirm that it started correctly.
                Please 'tail twistd.log' and look for a line that says
                'BuildMaster is running' to verify correct startup.
                """.format(self._timeout)))
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
            "--nodaemon",
            "--logfile=twistd.log",  # windows doesn't use the same default
            "--python=buildbot.tac"]

    if platformType != 'win32':
        # windows doesn't use pidfile option.
        argv.extend(["--pidfile="])

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


def py2Warning(config):
    if sys.version[0] == '2' and not config['quiet']:
        print(textwrap.dedent("""\
        WARNING: You are running Buildbot with Python 2.7.x !
        -----------------------------------------------------

        Python 2 is going unmaintained as soon as 2020: https://pythonclock.org/
        To prepare for that transition, we recommend upgrading your buildmaster to run on Python 3.6 now!
        Buildbot open source project is as well deprecating running buildmaster on Python 2 for better maintainability.

        Buildbot 2.0 going to be released in February 2019 will remove support for Python < 3.5
        https://github.com/buildbot/buildbot/issues/4439

        On most installations, switching to Python 3 can be accomplished by running the 2to3 tool over the master.cfg file.
        https://docs.python.org/3.7/library/2to3.html

        Note that the above applies only for the buildmaster.
        Workers will still support running under Python 2.7.
        Additionally, the buildmaster still supports workers using old versions of Buildbot.
        """))


def start(config):
    if not base.isBuildmasterDir(config['basedir']):
        return 1

    py2Warning(config)

    if config['nodaemon']:
        launchNoDaemon(config)
        return 0

    launch(config)

    # We don't have tail on windows
    if platformType == "win32" or config['quiet']:
        return 0

    # this is the parent
    timeout = config.get('start_timeout', None)
    if timeout is not None:
        try:
            timeout = float(timeout)
        except ValueError:
            print('Start timeout must be a number')
            return 1

    rc = Follower().follow(config['basedir'], timeout=timeout)
    return rc
