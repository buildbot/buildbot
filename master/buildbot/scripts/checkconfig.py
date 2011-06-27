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

import sys
import os
from twisted.internet import defer
from buildbot import master

class ConfigLoader(object):
    def __init__(self, basedir=os.getcwd(), configFileName="master.cfg"):
        self.basedir = os.path.abspath(basedir)
        self.configFileName = os.path.abspath(
                                os.path.join(basedir, configFileName))

    def load(self):
        d = defer.succeed(None)

        old_sys_path = sys.path[:]

        def loadcfg(_):
            sys.path.append(self.basedir)

            bmaster = master.BuildMaster(self.basedir, self.configFileName)
            return bmaster.loadConfig(open(self.configFileName, "r"),
                                      checkOnly=True)
        d.addCallback(loadcfg)

        # restore sys.path
        def fixup(x):
            sys.path[:] = old_sys_path
            return x
        d.addBoth(fixup)

        return d
