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

from buildslave.scripts import base
from buildslave.scripts import start
from buildslave.scripts import stop


def restart(config):
    quiet = config['quiet']
    basedir = config['basedir']

    if not base.isBuildslaveDir(basedir):
        return 1

    try:
        stop.stopSlave(basedir, quiet)
    except stop.SlaveNotRunning:
        if not quiet:
            log.msg("no old buildslave process found to stop")
    if not quiet:
        log.msg("now restarting buildslave process..")

    return start.startSlave(basedir, quiet, config['nodaemon'])
