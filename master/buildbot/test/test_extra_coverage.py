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

modules = [] # for the benefit of pyflakes

from buildbot import buildslave
modules.extend([buildslave])
from buildbot.changes import p4poller, svnpoller
modules.extend([p4poller, svnpoller])
from buildbot.clients import base, sendchange, tryclient
modules.extend([base, sendchange, tryclient])
from buildbot.process import mtrlogobserver, subunitlogobserver
modules.extend([mtrlogobserver, subunitlogobserver])
from buildbot.scripts import checkconfig, logwatcher, reconfig, runner, startup
modules.extend([checkconfig, logwatcher, reconfig, runner, startup])
from buildbot.status import client, html, status_gerrit, status_push
modules.extend([client, html, status_gerrit, status_push])
from buildbot.status import tinderbox, words
modules.extend([tinderbox, words])
from buildbot.status.web import baseweb, build, builder, buildstatus, changes
modules.extend([baseweb, build, builder, buildstatus, changes])
from buildbot.status.web import console, feeds, grid, logs, olpb, root, slaves
modules.extend([console, feeds, grid, logs, olpb, root, slaves])
from buildbot.status.web import status_json, step, tests, waterfall
modules.extend([status_json, step, tests, waterfall])
from buildbot.steps import dummy, master, maxq, python, python_twisted, subunit
modules.extend([dummy, master, maxq, python, python_twisted, subunit])
from buildbot.steps import trigger, vstudio
modules.extend([trigger, vstudio])
from buildbot.steps.package.rpm import rpmbuild, rpmlint, rpmspec
modules.extend([rpmbuild, rpmlint, rpmspec])
from buildbot.util import eventual, loop, monkeypatches
modules.extend([eventual, loop, monkeypatches])

# require gobject
#import buildbot.clients.gtkPanes
#import buildbot.clients.debug

# requires mercurial
#import buildbot.changes.hgbuildbot

# requires libboto
#import buildbot.ec2buildslave

# requires libvirt
#import buildbot.libvirtbuildslave

# requires pycrypto
#import buildbot.manhole
