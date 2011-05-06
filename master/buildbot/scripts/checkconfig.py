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
from shutil import copy, rmtree
from tempfile import mkdtemp
from twisted.internet import defer
from buildbot import master

class ConfigLoader(object):
    def __init__(self, basedir=os.getcwd(), configFileName="master.cfg"):
        self.basedir = os.path.abspath(basedir)
        self.configFileName = os.path.abspath(os.path.join(basedir, configFileName))

    def load(self):
        dir = os.getcwd()

        d = defer.succeed(None)

        def loadcfg(_):
            # Use a temporary directory since loadConfig() creates a bunch of
            # builder directories
            self.tempdir = mkdtemp()
            copy(self.configFileName, self.tempdir)

            os.chdir(self.tempdir)
            # Add the original directory to the library path so local module
            # imports work
            sys.path.append(self.basedir)

            bmaster = master.BuildMaster(self.basedir, self.configFileName)
            return bmaster.loadConfig(open(self.configFileName, "r"), checkOnly=True)
        d.addCallback(loadcfg)

        def cleanup(v):
            # clean up before passing on the exception
            os.chdir(dir)
            if os.path.exists(self.tempdir):
                rmtree(self.tempdir)
            return v # pass up the exception *or* result
        d.addBoth(cleanup)
        return d
