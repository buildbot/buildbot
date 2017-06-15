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
import datetime

from subprocess import PIPE
from subprocess import Popen
from subprocess import STDOUT


def gitDescribeToPep440(version):
    # git describe produce version in the form: v0.9.8-20-gf0f45ca
    # where 20 is the number of commit since last release, and gf0f45ca is the short commit id preceded by 'g'
    # we parse this a transform into a pep440 release version 0.9.9.dev20 (increment last digit and add dev before 20)

    VERSION_MATCH = re.compile(r'(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(-(?P<dev>\d+))?(-g(?P<commit>.+))?')
    v = VERSION_MATCH.search(version)
    if v:
        major = int(v.group('major'))
        minor = int(v.group('minor'))
        patch = int(v.group('patch'))
        if v.group('dev'):
            patch += 1
            dev = int(v.group('dev'))
            return "{}.{}.{}-dev{}".format(major, minor, patch, dev)
        return "{}.{}.{}".format(major, minor, patch)

    return v


def mTimeVersion(init_file):
    cwd = os.path.dirname(os.path.abspath(init_file))
    m = 0
    for root, dirs, files in os.walk(cwd):
        for f in files:
            m = max(os.path.getmtime(os.path.join(root, f)), m)
    d = datetime.datetime.fromtimestamp(m)
    return d.strftime("%Y.%m.%d")


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

    try:
        p = Popen(['git', 'describe', '--tags', '--always'], stdout=PIPE, stderr=STDOUT, cwd=cwd)
        out = p.communicate()[0]

        if (not p.returncode) and out:
            v = gitDescribeToPep440(str(out))
            if v:
                return v
    except OSError:
        pass

    try:
        # if we really can't find the version, we use the date of modification of the most recent file
        # docker hub builds cannot use git describe
        return mTimeVersion(init_file)
    except Exception:
        # bummer. lets report something
        return "latest"


version = getVersion(__file__)

__version__ = version
