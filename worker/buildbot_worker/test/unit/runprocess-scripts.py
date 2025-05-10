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

# This file contains scripts run by the test_runprocess tests.  Note that since
# this code runs in a different Python interpreter, it does not necessarily
# have access to any of the Buildbot source.  Functions here should be kept
# very simple!

from __future__ import annotations

import os
import select
import signal
import subprocess
import sys
import time
from typing import TYPE_CHECKING

import psutil

if TYPE_CHECKING:
    from typing import Callable
    from typing import NoReturn
    from typing import TypeVar

    _ScriptFnType = TypeVar("_ScriptFnType", bound=Callable[[], None])

# utils


def invoke_script(function: str, *args: str) -> None:
    cmd = [sys.executable, __file__, function, *list(args)]
    if os.name == 'nt':
        DETACHED_PROCESS = 0x00000008
        subprocess.Popen(
            cmd,
            shell=False,
            stdin=None,
            stdout=None,
            stderr=None,
            close_fds=True,
            creationflags=DETACHED_PROCESS,
        )
    else:
        subprocess.Popen(cmd, shell=False, stdin=None, stdout=None, stderr=None, close_fds=True)


def write_pidfile(pidfile: str) -> None:
    pidfile_tmp = pidfile + "~"
    f = open(pidfile_tmp, "w")
    f.write(str(os.getpid()))
    f.close()
    os.rename(pidfile_tmp, pidfile)


def sleep_forever() -> NoReturn:
    signal.alarm(110)  # die after 110 seconds
    while True:
        time.sleep(10)


script_fns: dict[str, Callable] = {}


def script(fn: _ScriptFnType) -> _ScriptFnType:
    script_fns[fn.__name__] = fn
    return fn


# scripts


@script
def write_pidfile_and_sleep() -> NoReturn:
    pidfile = sys.argv[2]
    write_pidfile(pidfile)
    sleep_forever()


@script
def spawn_child() -> NoReturn:
    parent_pidfile, child_pidfile = sys.argv[2:]
    invoke_script('write_pidfile_and_sleep', child_pidfile)
    write_pidfile(parent_pidfile)
    sleep_forever()


@script
def wait_for_pid_death_and_write_pidfile_and_sleep() -> NoReturn:
    wait_pid = int(sys.argv[2])
    pidfile = sys.argv[3]

    while psutil.pid_exists(wait_pid):
        time.sleep(0.01)

    write_pidfile(pidfile)
    sleep_forever()


@script
def double_fork() -> NoReturn:
    if os.name == 'posix':
        # when using a PTY, the child process will get SIGHUP when the
        # parent process exits, so ignore that.
        signal.signal(signal.SIGHUP, signal.SIG_IGN)

    parent_pidfile, child_pidfile = sys.argv[2:]
    parent_pid = os.getpid()

    invoke_script('wait_for_pid_death_and_write_pidfile_and_sleep', str(parent_pid), child_pidfile)
    write_pidfile(parent_pidfile)
    sys.exit(0)


@script
def assert_stdin_closed() -> None:
    # EOF counts as readable data, so we should see stdin in the readable list,
    # although it may not appear immediately, and select may return early
    bail_at = time.time() + 10
    while True:
        r, _, __ = select.select([0], [], [], 0.01)
        if r == [0]:
            return  # success!
        if time.time() > bail_at:
            raise AssertionError()  # failure :(


# make sure this process dies if necessary

if not hasattr(signal, 'alarm'):
    signal.alarm = lambda t: 0
signal.alarm(110)  # die after 110 seconds

# dispatcher

script_fns[sys.argv[1]]()
