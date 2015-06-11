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
             "slave-side source checkout for '%s' is no longer supported by "
             "build slave of version %s\n" % (self.name, buildslave.version)})
        self.sendStatus({"rc": 1})


class Svn(RemovedSourceCommand):
    name = "git"


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
