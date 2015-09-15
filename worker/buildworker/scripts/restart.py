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

from twisted.python import log

from buildworker.scripts import base
from buildworker.scripts import start
from buildworker.scripts import stop


def restart(config):
    quiet = config['quiet']
    basedir = config['basedir']

    if not base.isBuildworkerDir(basedir):
        return 1

    try:
        stop.stopWorker(basedir, quiet)
    except stop.WorkerNotRunning:
        if not quiet:
            log.msg("no old buildworker process found to stop")
    if not quiet:
        log.msg("now restarting buildworker process..")

    return start.startWorker(basedir, quiet, config['nodaemon'])
