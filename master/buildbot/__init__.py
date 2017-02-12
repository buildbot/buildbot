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
#
# Keep in sync with slave/buildslave/__init__.py
#
# We can't put this method in utility modules, because they import dependency packages

from __future__ import division
from __future__ import print_function

import os
import re

from subprocess import PIPE
from subprocess import Popen
from subprocess import STDOUT


def getVersion(init_file):
    """
    Return BUILDBOT_VERSION environment variable, content of VERSION file, git
    tag or 'latest'
    """

    try:
        return os.environ['BUILDBOT_VERSION']
    except KeyError:
        pass

    try:
        cwd = os.path.dirname(os.path.abspath(init_file))
        fn = os.path.join(cwd, 'VERSION')
        with open(fn) as f:
            return f.read().strip()
    except IOError:
        pass

    # accept version to be coded with 2 or 3 parts (X.Y or X.Y.Z),
    # no matter the number of digits for X, Y and Z
    VERSION_MATCH = re.compile(r'(\d+\.\d+(\.\d+)?(\w|-)*)')

    try:
        p = Popen(['git', 'describe', '--tags', '--always'], stdout=PIPE, stderr=STDOUT, cwd=cwd)
        out = p.communicate()[0]

        if (not p.returncode) and out:
            v = VERSION_MATCH.search(str(out))
            if v:
                return v.group(1)
    except OSError:
        pass

    return "latest"


version = getVersion(__file__)

__version__ = version
