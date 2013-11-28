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

from buildbot.steps.source.base import Source
from buildbot.steps.source.oldsource import BK
from buildbot.steps.source.oldsource import Bzr
from buildbot.steps.source.oldsource import CVS
from buildbot.steps.source.oldsource import Darcs
from buildbot.steps.source.oldsource import Git
from buildbot.steps.source.oldsource import Mercurial
from buildbot.steps.source.oldsource import Monotone
from buildbot.steps.source.oldsource import P4
from buildbot.steps.source.oldsource import Repo
from buildbot.steps.source.oldsource import SVN
from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version

warningString = "The slave-side %s step is deprecated and will be removed in a future version.  Please switch to the corresponding master-side step."

oldClasses = ["CVS", "SVN", "Git", "Darcs", "Repo", "Bzr", "Mercurial", "P4",
              "Monotone", "BK"]

for oldClass in oldClasses:
    deprecatedModuleAttribute(Version("Buildbot", 0, 8, 9),
                              warningString % (oldClass),
                              "buildbot.steps.source", oldClass)

_hush_pyflakes = [Source, CVS, SVN,
                  Git, Darcs, Repo, Bzr, Mercurial, P4, Monotone, BK]
