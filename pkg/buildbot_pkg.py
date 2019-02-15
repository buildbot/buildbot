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
from __future__ import print_function

# Method to add build step taken from here
# https://seasonofcode.com/posts/how-to-add-custom-build-steps-and-commands-to-setuppy.html
import datetime
import distutils.cmd
import os
import re
import subprocess
import sys
from distutils.version import LooseVersion
from subprocess import PIPE
from subprocess import STDOUT
from subprocess import Popen

import setuptools.command.build_py
import setuptools.command.egg_info
from setuptools import setup

old_listdir = os.listdir


def listdir(path):
    # patch listdir to avoid looking into node_modules
    l = old_listdir(path)
    if "node_modules" in l:
        l.remove("node_modules")
    return l
os.listdir = listdir


def check_output(cmd):
    """Version of check_output which does not throw error"""
    popen = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    out = popen.communicate()[0].strip()
    if not isinstance(out, str):
        out = out.decode(sys.stdout.encoding)
    return out


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
            return "{}.{}.{}-dev{}".format(major, minor, patch, dev)
        if v.group('post'):
            return "{}.{}.{}.post{}".format(major, minor, patch, v.group('post'))
        return "{}.{}.{}".format(major, minor, patch)

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


# JS build strategy:
#
# Obviously, building javascript with setuptools is not really something supported initially
#
# The goal of this hack are:
# - override the distutils command to insert our js build
# - has very small setup.py
#
# from buildbot_pkg import setup_www
#
# setup_www(
#   ...
#    packages=["buildbot_myplugin"]
# )
#
# We need to override the first command done, so that source tree is populated very soon,
# as well as version is found from git tree or "VERSION" file
#
# This supports following setup.py commands:
#
# - develop, via egg_info
# - install, via egg_info
# - sdist, via egg_info
# - bdist_wheel, via build
# This is why we override both egg_info and build, and the first run build
# the js.

class BuildJsCommand(distutils.cmd.Command):
    """A custom command to run JS build."""

    description = 'run JS build'
    already_run = False

    def initialize_options(self):
        """Set default values for options."""

    def finalize_options(self):
        """Post-process options."""

    def run(self):
        """Run command."""
        if self.already_run:
            return
        package = self.distribution.packages[0]
        if os.path.exists("gulpfile.js") or os.path.exists("webpack.config.js"):
            yarn_version = check_output("yarn --version")
            npm_version = check_output("npm -v")
            print("yarn:", yarn_version, "npm: ", npm_version)
            if yarn_version != "":
                npm_bin = check_output("yarn bin").strip()
            else:
                assert npm_version != "", "need nodejs and one of npm or yarn installed in current PATH"
                assert LooseVersion(npm_version) >= LooseVersion(
                    "1.4"), "npm < 1.4 (%s)" % (npm_version)
                npm_bin = check_output("npm bin").strip()

            commands = []

            # if we find yarn, then we use it as it is much faster
            if yarn_version != "":
                commands.append(['yarn', 'install', '--pure-lockfile'])
            else:
                commands.append(['npm', 'install'])

            if os.path.exists("gulpfile.js"):
                commands.append([os.path.join(npm_bin, "gulp"), 'prod', '--notests'])
            elif os.path.exists("webpack.config.js"):
                commands.append([os.path.join(npm_bin, "webpack"), '-p'])

            shell = bool(os.name == 'nt')

            for command in commands:
                self.announce(
                    'Running command: %s' % str(" ".join(command)),
                    level=distutils.log.INFO)
                subprocess.call(command, shell=shell)

        self.copy_tree(os.path.join(package, 'static'), os.path.join(
            "build", "lib", package, "static"))

        with open(os.path.join("build", "lib", package, "VERSION"), "w") as f:
            f.write(self.distribution.metadata.version)

        with open(os.path.join(package, "VERSION"), "w") as f:
            f.write(self.distribution.metadata.version)

        self.already_run = True


class BuildPyCommand(setuptools.command.build_py.build_py):
    """Custom build command."""

    def run(self):
        self.run_command('build_js')
        super().run()


class EggInfoCommand(setuptools.command.egg_info.egg_info):
    """Custom egginfo command."""

    def run(self):
        self.run_command('build_js')
        super().run()


def setup_www_plugin(**kw):
    package = kw['packages'][0]
    if 'version' not in kw:
        kw['version'] = getVersion(os.path.join(package, "__init__.py"))

    setup(cmdclass=dict(
        egg_info=EggInfoCommand,
        build_py=BuildPyCommand,
        build_js=BuildJsCommand),
        **kw)
