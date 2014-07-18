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

"""
Buildbot plugin infrastructure
"""

from buildbot.plugins.db import get_plugins
from buildbot.interfaces import IBuildSlave
from buildbot.interfaces import IChangeSource
from buildbot.interfaces import IScheduler

# Names here match the names of the corresponding Buildbot module, hence
# 'changes', 'schedulers', but 'buildslave'
changes = get_plugins('change_source', IChangeSource)
schedulers = get_plugins('scheduler', IScheduler)
buildslave = get_plugins('build_slave', IBuildSlave)
