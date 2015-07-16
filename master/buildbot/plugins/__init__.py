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

from buildbot import statistics
from buildbot.interfaces import IBuildSlave
from buildbot.interfaces import IBuildStep
from buildbot.interfaces import IChangeSource
from buildbot.interfaces import IScheduler
from buildbot.plugins.db import get_plugins


__all__ = ['changes', 'schedulers', 'buildslave', 'steps', 'util', 'reporters', 'statistics']


# Names here match the names of the corresponding Buildbot module, hence
# 'changes', 'schedulers', but 'buildslave'
changes = get_plugins('changes', IChangeSource)
schedulers = get_plugins('schedulers', IScheduler)
buildslave = get_plugins('buildslave', IBuildSlave)
steps = get_plugins('steps', IBuildStep)
util = get_plugins('util', None)
reporters = get_plugins('reporters', None)
