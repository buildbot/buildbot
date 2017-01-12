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

# this file imports a number of source files that are not
# included in the coverage because none of the tests import
# them; this results in a more accurate total coverage percent.

from __future__ import absolute_import
from __future__ import print_function

from buildbot_worker.scripts import logwatcher

modules = []  # for the benefit of pyflakes
modules.extend([logwatcher])
