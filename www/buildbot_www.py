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

import os
import sys

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

class EntryPoint(object):
    def __init__(self):
        self.name = "Buildbot UI"

        # the rest depends on the context we're executing in
        if context == 'SRC':
            self.version = 'source'
            self.static_dir = os.path.abspath(sibpath('src'))
        elif context == 'BUILT':
            self.version = 'source'
            self.static_dir = os.path.abspath(sibpath('built'))
        else: # context == 'INSTALLED'
            instdir = os.path.join(sys.prefix, 'share', 'buildbot', 'built')
            verfile = os.path.join(instdir, 'buildbot-version.txt')
            self.version = open(verfile).read().strip()
            self.static_dir = instdir

        # as a sanity-check, ensure that the haml templates are built.  This
        # should only fail in SRC context, but it can't hurt to check
        # everywhere
        if not os.path.exists(os.path.join(self.static_dir,
                                    "bb", "ui", "templates", "home.haml.js")):
            raise ImportError("HAML files are not built; run ./build.sh --haml-only")

        self.index_html = open(os.path.join(self.static_dir, 'index.html')).read()

# create the interface for the setuptools entry point
ep = EntryPoint()
