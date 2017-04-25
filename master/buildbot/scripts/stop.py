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

import errno
import os
import signal
import time

from twisted.python.runtime import platformType

from buildbot.scripts import base


def stop(config, signame="TERM", wait=None):
    basedir = config['basedir']
    quiet = config['quiet']

    if wait is None:
        wait = not config['no-wait']

    if config['clean']:
        signame = 'USR1'

    if not base.isBuildmasterDir(config['basedir']):
        return 1

    pidfile = os.path.join(basedir, 'twistd.pid')
    try:
        with open(pidfile, "rt") as f:
            pid = int(f.read().strip())
    except Exception:
        if not config['quiet']:
            print("buildmaster not running")
        return 0

    signum = getattr(signal, "SIG" + signame)
    try:
        os.kill(pid, signum)
    except OSError as e:
        if e.errno != errno.ESRCH and platformType != "win32":
            raise
        else:
            if not config['quiet']:
                print("buildmaster not running")
            try:
                os.unlink(pidfile)
            except OSError:
                pass
            return 0

    if not wait:
        if not quiet:
            print("sent SIG%s to process" % signame)
        return 0

    time.sleep(0.1)

    # poll once per second until twistd.pid goes away, up to 10 seconds,
    # unless we're doing a clean stop, in which case wait forever
    count = 0
    while count < 10 or config['clean']:
        try:
            os.kill(pid, 0)
        except OSError:
            if not quiet:
                print("buildbot process %d is dead" % pid)
            return 0
        time.sleep(1)
        count += 1
    if not quiet:
        print("never saw process go away")
    return 1
