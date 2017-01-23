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

from buildbot.scripts import base
from buildbot.scripts import start
from buildbot.scripts import stop


def restart(config):
    basedir = config['basedir']
    quiet = config['quiet']

    if not base.isBuildmasterDir(basedir):
        return 1

    if stop.stop(config, wait=True) != 0:
        return 1
    if not quiet:
        print("now restarting buildbot process..")
    return start.start(config)
