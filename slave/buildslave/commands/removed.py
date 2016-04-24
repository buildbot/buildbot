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


import buildslave
from buildslave.commands import base


class RemovedSourceCommand(base.SourceBaseCommand):

    def start(self):
        self.sendStatus(
            {"header":
             "slave-side source checkout for '{0}' is no longer supported by "
             "build slave of version {1}\n"
             "\n"
             "Since BuildBot 0.9 old source checkout method with logic on slave-side\n"
             "buildbot.steps.source.{0} was removed (deprecated since BuildBot 0.8)\n"
             "\n"
             "Instead please use new method which has its logic on master-side and has unified params list.\n"
             "Using the plugin infrastructure it's available as buildbot.plugins.{0}\n"
             "\n"
             .format(self.name, buildslave.version)})
        self.sendStatus({"rc": 1})


class Svn(RemovedSourceCommand):
    name = "SVN"


class Bk(RemovedSourceCommand):
    name = "Bk"


class Cvs(RemovedSourceCommand):
    name = "Cvs"


class Darcs(RemovedSourceCommand):
    name = "darcs"


class Git(RemovedSourceCommand):
    name = "git"


class Bzr(RemovedSourceCommand):
    name = "bzr"


class Hg(RemovedSourceCommand):
    name = "hg"


class P4(RemovedSourceCommand):
    name = "p4"


class Mtn(RemovedSourceCommand):
    name = "mtn"
