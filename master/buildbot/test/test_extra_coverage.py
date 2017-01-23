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

from buildbot import worker
from buildbot.changes import p4poller
from buildbot.changes import svnpoller
from buildbot.clients import base
from buildbot.clients import sendchange
from buildbot.clients import tryclient
from buildbot.process import subunitlogobserver
from buildbot.scripts import checkconfig
from buildbot.scripts import logwatcher
from buildbot.scripts import reconfig
from buildbot.scripts import runner
from buildbot.status import client
from buildbot.steps import master
from buildbot.steps import maxq
from buildbot.steps import python
from buildbot.steps import python_twisted
from buildbot.steps import subunit
from buildbot.steps import trigger
from buildbot.steps import vstudio
from buildbot.steps.package.rpm import rpmbuild
from buildbot.steps.package.rpm import rpmlint
from buildbot.steps.package.rpm import rpmspec
from buildbot.util import eventual

modules = []  # for the benefit of pyflakes
modules.extend([worker])
modules.extend([p4poller, svnpoller])
modules.extend([base, sendchange, tryclient])
modules.extend([subunitlogobserver])
modules.extend([checkconfig, logwatcher, reconfig, runner])
modules.extend([client])
modules.extend([master, maxq, python, python_twisted, subunit])
modules.extend([trigger, vstudio])
modules.extend([rpmbuild, rpmlint, rpmspec])
modules.extend([eventual])
