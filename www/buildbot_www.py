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
from twisted.python import util

name = "Buildbot UI"

# several cases here:
# we are in a pre-built environment: we give the bot master path to the pre-built files
# we are in a python setup.py develop mode: we give the bot master path to the src files
paths = [ os.path.join(sys.prefix, 'share', 'buildbot', 'built'),
          util.sibpath(__file__,"src") ]

for static_dir in paths:
    if os.path.isdir(static_dir):
        def read_file(fn, default=None):
            fn = os.path.join(static_dir, fn)
            if not os.path.exists(fn) and default is not None:
                return default
            f = open(fn,"r")
            data = f.read()
            f.close()
            return data
        version = read_file('buildbot-version.txt', default="developer").strip()
        index_html = read_file("index.html")
        break

__all__ = [name, version, static_dir, index_html]
