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
from os.path import isfile

from buildbot import master

class ConfigLoader(master.BuildMaster):
    def __init__(self, basedir=os.getcwd(), configFileName="master.cfg"):
        master.BuildMaster.__init__(self, basedir, configFileName)
        configFileName = os.path.join(basedir, configFileName)
        dir = os.getcwd()
        # Use a temporary directory since loadConfig() creates a bunch of
        # directories and compiles .py files
        tempdir = mkdtemp()
        try:
            copy(configFileName, tempdir)
            for entry in os.listdir("."):
                # Any code in a subdirectory will _not_ be copied! This is a bug
                if isfile(entry) and not entry.startswith("twistd.log"):
                    copy(entry, tempdir)
        except:
            raise

        try:
            os.chdir(tempdir)
            # Add the temp directory to the library path so local modules work
            sys.path.append(tempdir)
            configFile = open(configFileName, "r")
            self.loadConfig(configFile, check_synchronously_only=True)
        except:
            # clean up before passing on the exception
            os.chdir(dir)
            rmtree(tempdir)
            raise
        os.chdir(dir)
        rmtree(tempdir)
