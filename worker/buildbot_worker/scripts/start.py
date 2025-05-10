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
from __future__ import annotations

import os
import sys
import time
from typing import TYPE_CHECKING
from typing import cast

from buildbot_worker.scripts import base
from buildbot_worker.util import rewrap

if TYPE_CHECKING:
    from typing import Any

    from twisted.internet.interfaces import IReactorCore
    from twisted.python.failure import Failure


class Follower:
    def follow(self) -> int:
        from twisted.internet import reactor

        from buildbot_worker.scripts.logwatcher import LogWatcher

        self.rc = 0
        print("Following twistd.log until startup finished..")
        lw = LogWatcher("twistd.log")
        d = lw.start()
        d.addCallbacks(self._success, self._failure)
        cast("IReactorCore", reactor).run()
        return self.rc

    def _success(self, processtype: str) -> None:
        from twisted.internet import reactor

        print(f"The {processtype} appears to have (re)started correctly.")
        self.rc = 0
        cast("IReactorCore", reactor).stop()

    def _failure(self, why: Failure) -> None:
        from twisted.internet import reactor

        from buildbot_worker.scripts.logwatcher import WorkerTimeoutError

        if why.check(WorkerTimeoutError):
            print(
                rewrap("""\
                The worker took more than 10 seconds to start and/or connect
                to the buildmaster, so we were unable to confirm that it
                started and connected correctly.
                Please 'tail twistd.log' and look for a line that says
                'message from master: attached' to verify correct startup.
                If you see a bunch of messages like 'will retry in 6 seconds',
                your worker might not have the correct hostname or portnumber
                for the buildmaster, or the buildmaster might not be running.
                If you see messages like
                   'Failure: twisted.cred.error.UnauthorizedLogin'
                then your worker might be using the wrong botname or password.
                Please correct these problems and then restart the worker.
                """)
            )
        else:
            print(
                rewrap("""\
                Unable to confirm that the worker started correctly.
                You may need to stop it, fix the config file, and restart.
                """)
            )
            print(why)
        self.rc = 1
        cast("IReactorCore", reactor).stop()


def startCommand(config: dict[str, Any]) -> int:
    basedir = config['basedir']
    if not base.isWorkerDir(basedir):
        return 1

    return startWorker(basedir, config['quiet'], config['nodaemon'])


def startWorker(basedir: str, quiet: bool, nodaemon: bool) -> int:
    """
    Start worker process.

    Fork and start twisted application described in basedir buildbot.tac file.
    Print it's log messages to stdout for a while and try to figure out if
    start was successful.

    If quiet or nodaemon parameters are True, or we are running on a win32
    system, will not fork and log will not be printed to stdout.

    @param  basedir: worker's basedir path
    @param    quiet: don't display startup log messages
    @param nodaemon: don't daemonize (stay in foreground)
    @return: 0 if worker was successfully started,
             1 if we are not sure that worker started successfully
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
    return launch(nodaemon)


def launch(nodaemon: bool) -> int:
    sys.path.insert(0, os.path.abspath(os.getcwd()))

    # see if we can launch the application without actually having to
    # spawn twistd, since spawning processes correctly is a real hassle
    # on windows.
    from twisted.python.runtime import platformType
    from twisted.scripts.twistd import run

    argv = [
        "twistd",
        "--no_save",
        "--logfile=twistd.log",  # windows doesn't use the same default
        "--python=buildbot.tac",
    ]
    if nodaemon:
        argv.extend(["--nodaemon"])
        if platformType != 'win32':
            # windows doesn't use pidfile option.
            argv.extend(["--pidfile="])

    sys.argv = argv
    run()
    return 0
