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
# We can't put this method in utility modules, because they import dependency packages


import datetime
import os
import re
from subprocess import PIPE
from subprocess import STDOUT
from subprocess import Popen


def gitDescribeToPep440(version):
    # git describe produce version in the form: v0.9.8-20-gf0f45ca
    # where 20 is the number of commit since last release, and gf0f45ca is the short commit id
    # preceded by 'g' we parse this a transform into a pep440 release version 0.9.9.dev20
    # (increment last digit and add dev before 20)

    VERSION_MATCH = re.compile(
        r'(?P<major>\d+)\.(?P<minor>\d+)\.(?P<patch>\d+)(\.post(?P<post>\d+))?(-(?P<dev>\d+))?(-g(?P<commit>.+))?'
    )
    v = VERSION_MATCH.search(version)
    if v:
        major = int(v.group('major'))
        minor = int(v.group('minor'))
        patch = int(v.group('patch'))
        if v.group('dev'):
            patch += 1
            dev = int(v.group('dev'))
            return f"{major}.{minor}.{patch}.dev{dev}"
        if v.group('post'):
            return f"{major}.{minor}.{patch}.post{v.group('post')}"
        return f"{major}.{minor}.{patch}"

    return v


def mTimeVersion(init_file):
    cwd = os.path.dirname(os.path.abspath(init_file))
    m = 0
    for root, _, files in os.walk(cwd):
        for f in files:
            m = max(os.path.getmtime(os.path.join(root, f)), m)
    d = datetime.datetime.fromtimestamp(m, datetime.timezone.utc)
    return d.strftime("%Y.%m.%d")


def getVersionFromArchiveId(git_archive_id='$Format:%ct %(describe:abbrev=10)$'):
    """Extract the tag if a source is from git archive.

    When source is exported via `git archive`, the git_archive_id init value is modified
    and placeholders are expanded to the "archived" revision:

        %ct: committer date, UNIX timestamp
        %(describe:abbrev=10): git-describe output, always abbreviating to 10 characters of commit ID.
                               e.g. v3.10.0-850-g5bf957f89

    See man gitattributes(5) and git-log(1) (PRETTY FORMATS) for more details.
    """
    # mangle the magic string to make sure it is not replaced by git archive
    if not git_archive_id.startswith('$For' + 'mat:'):
        # source was modified by git archive, try to parse the version from
        # the value of git_archive_id

        tstamp, _, describe_output = git_archive_id.strip().partition(' ')
        if describe_output:
            # archived revision is tagged, use the tag
            return gitDescribeToPep440(describe_output)

        # archived revision is not tagged, use the commit date
        d = datetime.datetime.fromtimestamp(int(tstamp), datetime.timezone.utc)
        return d.strftime('%Y.%m.%d')
    return None


def getVersion(init_file):
    """
    Return BUILDBOT_VERSION environment variable, content of VERSION file, git
    tag or '0.0.0'  meaning we could not find the version, but the output still has to be valid
    """

    try:
        return os.environ['BUILDBOT_VERSION']
    except KeyError:
        pass

    try:
        cwd = os.path.dirname(os.path.abspath(init_file))
        fn = os.path.join(cwd, 'VERSION')
        with open(fn, encoding='utf-8') as f:
            return f.read().strip()
    except OSError:
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
        # if we really can't find the version, we use the date of modification of the most recent
        # file docker hub builds cannot use git describe
        return mTimeVersion(init_file)
    except Exception:
        # bummer. lets report something
        return "0.0.0"


version = getVersion(__file__)

__version__ = version
