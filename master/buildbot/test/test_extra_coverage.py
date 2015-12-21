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

modules = []  # for the benefit of pyflakes

from buildbot import buildslave
modules.extend([buildslave])
from buildbot.changes import p4poller
from buildbot.changes import svnpoller
modules.extend([p4poller, svnpoller])
from buildbot.clients import base
from buildbot.clients import sendchange
from buildbot.clients import tryclient
modules.extend([base, sendchange, tryclient])
from buildbot.process import subunitlogobserver
modules.extend([subunitlogobserver])
from buildbot.scripts import checkconfig
from buildbot.scripts import logwatcher
from buildbot.scripts import reconfig
from buildbot.scripts import runner
modules.extend([checkconfig, logwatcher, reconfig, runner])
from buildbot.status import client
modules.extend([client])
from buildbot.steps import master
from buildbot.steps import maxq
from buildbot.steps import python
from buildbot.steps import python_twisted
from buildbot.steps import subunit
modules.extend([master, maxq, python, python_twisted, subunit])
from buildbot.steps import trigger
from buildbot.steps import vstudio
modules.extend([trigger, vstudio])
from buildbot.steps.package.rpm import rpmbuild
from buildbot.steps.package.rpm import rpmlint
from buildbot.steps.package.rpm import rpmspec
modules.extend([rpmbuild, rpmlint, rpmspec])
from buildbot.util import eventual
modules.extend([eventual])

# requires libboto
# import buildbot.ec2buildslave

# requires libvirt
# import buildbot.libvirtbuildslave

# requires pycrypto
# import buildbot.manhole
