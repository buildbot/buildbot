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
from buildbot import config

class ConfigLoader(object):
    def __init__(self, basedir=os.getcwd(), configFileName="master.cfg"):
        self.basedir = os.path.abspath(basedir)
        self.configFileName = os.path.abspath(
                                os.path.join(basedir, configFileName))

    def load(self, quiet=False):
        try:
            config.MasterConfig.loadConfig(
                    self.basedir, self.configFileName)
        except config.ConfigErrors, e:
            if not quiet:
                print >> sys.stderr, "Configuration Errors:"
                for e in e.errors:
                    print >> sys.stderr, "  " + e
            return 1

        if not quiet:
            print "Config file is good!"
        return 0

def checkconfig(config):
    quiet = config.get('quiet')
    configFileName = config.get('configFile')

    if os.path.isdir(configFileName):
        cl = ConfigLoader(basedir=configFileName)
    else:
        cl = ConfigLoader(configFileName=configFileName)

    return cl.load(quiet=quiet)
