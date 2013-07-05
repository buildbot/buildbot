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
from buildbot.scripts.base import getConfigFileFromTac

def _loadConfig(basedir, configFile, quiet):
    try:
        config.MasterConfig.loadConfig(
                basedir, configFile)
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
    configFile = config.get('configFile')

    if os.path.isdir(configFile):
        basedir = configFile
        try:
            configFile = getConfigFileFromTac(basedir)
        except (SyntaxError, ImportError), e:
            if not quiet:
                print "Unable to load 'buildbot.tac' from '%s':" % basedir
                print e
            return 1
    else:
        basedir = os.getcwd()

    return _loadConfig(basedir=basedir, configFile=configFile, quiet=quiet)


__all__ = ['checkconfig']
