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
import time

from buildbot_worker.scripts import base


class WorkerNotRunning(Exception):

    """
    raised when trying to stop worker process that is not running
    """


def stopWorker(basedir, quiet, signame="TERM"):
    """
    Stop worker process by sending it a signal.

    Using the specified basedir path, read worker process's pid file and
    try to terminate that process with specified signal.

    @param basedir: worker's basedir path
    @param   quite: if False, don't print any messages to stdout
    @param signame: signal to send to the worker process

    @raise WorkerNotRunning: if worker pid file is not found
    """
    import signal

    os.chdir(basedir)
    try:
        f = open("twistd.pid", "rt")
    except IOError:
        raise WorkerNotRunning()

    pid = int(f.read().strip())
    signum = getattr(signal, "SIG" + signame)
    timer = 0
    try:
        os.kill(pid, signum)
    except OSError as e:
        if e.errno != 3:
            raise

    time.sleep(0.1)
    while timer < 10:
        # poll once per second until twistd.pid goes away, up to 10 seconds
        try:
            os.kill(pid, 0)
        except OSError:
            if not quiet:
                print("worker process %d is dead" % pid)
            return 0
        timer += 1
        time.sleep(1)
    if not quiet:
        print("never saw process go away")
    return 1


def stop(config, signame="TERM"):
    quiet = config['quiet']
    basedir = config['basedir']

    if not base.isWorkerDir(basedir):
        return 1

    try:
        return stopWorker(basedir, quiet, signame)
    except WorkerNotRunning:
        if not quiet:
            print("worker not running")
        return 0
