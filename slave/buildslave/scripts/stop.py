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
import time

from twisted.python import log

from buildslave.scripts import base


class SlaveNotRunning(Exception):

    """
    raised when trying to stop slave process that is not running
    """


def stopSlave(basedir, quiet, signame="TERM"):
    """
    Stop slave process by sending it a signal.

    Using the specified basedir path, read slave process's pid file and
    try to terminate that process with specified signal.

    @param basedir: buildslave's basedir path
    @param   quite: if False, don't print any messages to stdout
    @param signame: signal to send to the slave process

    @raise SlaveNotRunning: if slave pid file is not found
    """
    import signal

    os.chdir(basedir)
    try:
        f = open("twistd.pid", "rt")
    except IOError:
        raise SlaveNotRunning()

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
                log.msg("buildslave process %d is dead" % pid)
            return
        timer += 1
        time.sleep(1)
    if not quiet:
        log.msg("never saw process go away")


def stop(config, signame="TERM"):
    quiet = config['quiet']
    basedir = config['basedir']

    if not base.isBuildslaveDir(basedir):
        return 1

    try:
        stopSlave(basedir, quiet, signame)
    except SlaveNotRunning:
        if not quiet:
            log.msg("buildslave not running")

    return 0
