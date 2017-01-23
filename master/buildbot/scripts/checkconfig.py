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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import os
import sys

from buildbot import config
from buildbot.scripts.base import getConfigFileFromTac
from buildbot.util import in_reactor


def _loadConfig(basedir, configFile, quiet):
    try:
        config.FileLoader(basedir, configFile).loadConfig()
    except config.ConfigErrors as e:
        if not quiet:
            print("Configuration Errors:", file=sys.stderr)
            for e in e.errors:
                print("  " + e, file=sys.stderr)
        return 1

    if not quiet:
        print("Config file is good!")
    return 0


@in_reactor
def checkconfig(config):
    quiet = config.get('quiet')
    configFile = config.get('configFile', os.getcwd())

    if os.path.isdir(configFile):
        basedir = configFile
        try:
            configFile = getConfigFileFromTac(basedir, quiet=quiet)
        except Exception:
            if not quiet:
                # the exception is already printed in base.py
                print("Unable to load 'buildbot.tac' from '%s':" % basedir)
            return 1
    else:
        basedir = os.getcwd()

    return _loadConfig(basedir=basedir, configFile=configFile, quiet=quiet)


__all__ = ['checkconfig']
