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
# Keep in sync with master/buildbot/__init__.py
#
# We can't put this method in utility modules, because they import dependency packages
#

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

    VERSION_MATCH = re.compile(r'(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(\.post(?P<post>\d+))?(-(?P<dev>\d+))?(-g(?P<commit>.+))?')
    v = VERSION_MATCH.search(version)
    if v:
        major = int(v.group('major'))
        minor = int(v.group('minor'))
        patch = int(v.group('patch'))
        if v.group('dev'):
            patch += 1
            dev = int(v.group('dev'))
            return "{0}.{1}.{2}-dev{3}".format(major, minor, patch, dev)
        if v.group('post'):
            return "{0}.{1}.{2}.post{3}".format(major, minor, patch, v.group('post'))
        return "{0}.{1}.{2}".format(major, minor, patch)

    return v


def mTimeVersion(init_file):
    cwd = os.path.dirname(os.path.abspath(init_file))
    m = 0
    for root, dirs, files in os.walk(cwd):
        for f in files:
            m = max(os.path.getmtime(os.path.join(root, f)), m)
    d = datetime.datetime.utcfromtimestamp(m)
    return d.strftime("%Y.%m.%d")


def getVersionFromArchiveId(git_archive_id='$Format:%ct %d$'):
    """ Extract the tag if a source is from git archive.

        When source is exported via `git archive`, the git_archive_id init value is modified
        and placeholders are expanded to the "archived" revision:

            %ct: committer date, UNIX timestamp
            %d: ref names, like the --decorate option of git-log

        See man gitattributes(5) and git-log(1) (PRETTY FORMATS) for more details.
    """
    # mangle the magic string to make sure it is not replaced by git archive
    if not git_archive_id.startswith('$For''mat:'):
        # source was modified by git archive, try to parse the version from
        # the value of git_archive_id

        match = re.search(r'tag:\s*v([^,)]+)', git_archive_id)
        if match:
            # archived revision is tagged, use the tag
            return gitDescribeToPep440(match.group(1))

        # archived revision is not tagged, use the commit date
        tstamp = git_archive_id.strip().split()[0]
        d = datetime.datetime.utcfromtimestamp(int(tstamp))
        return d.strftime('%Y.%m.%d')
    return None


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

    version = getVersionFromArchiveId()
    if version is not None:
        return version

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
