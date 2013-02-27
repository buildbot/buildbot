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
# Portions copyright The Dojo Foundation

import os
import sys

from twisted.web import static

def sibpath(*elts):
    return os.path.join(os.path.dirname(__file__), *elts)

# (see comments in setup.py about contexts)
#
# this script never runs in the SDIST state, so if src/ is missing,
# then we're INSTALLED
src_exists = os.path.isdir(sibpath('src'))
built_exists = os.path.isdir(sibpath('built'))
if src_exists:
    if not built_exists:
        context = 'SRC'
    else:
        context = 'BUILT'
else:
    context = 'INSTALLED'

class Application(object):
    def __init__(self):
        self.description = "Buildbot UI"

        # the rest depends on the context we're executing in
        if context == 'SRC':
            raise Exception("cannot run in source mode! you need to first call grunt dev.")
        elif context == 'BUILT':
            self.version = 'source'
            self.static_dir = os.path.abspath(sibpath('built'))
        else: # context == 'INSTALLED'
            instdir = os.path.join(sys.prefix, 'share', 'buildbot', 'dist')
            verfile = os.path.join(instdir, 'buildbot-version.txt')
            self.version = open(verfile).read().strip()
            self.static_dir = instdir

        self.resource = static.File(self.static_dir)


# create the interface for the setuptools entry point
ep = Application()
