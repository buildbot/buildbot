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

from twisted.python import log

from buildslave.scripts import base


def upgradeSlave(config):
    basedir = os.path.expanduser(config['basedir'])

    if not base.isBuildslaveDir(basedir):
        return 1

    buildbot_tac = open(os.path.join(basedir, "buildbot.tac")).read()
    new_buildbot_tac = buildbot_tac.replace(
        "from buildbot.slave.bot import BuildSlave",
        "from buildslave.bot import BuildSlave")
    if new_buildbot_tac != buildbot_tac:
        open(os.path.join(basedir, "buildbot.tac"), "w").write(
            new_buildbot_tac)
        log.msg("buildbot.tac updated")
    else:
        log.msg("No changes made")

    return 0
