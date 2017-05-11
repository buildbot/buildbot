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
import distutils.cmd
import os
import subprocess
import sys
from distutils.version import LooseVersion

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


def getVersion(init_file):
    try:
        return os.environ['BUILDBOT_VERSION']
    except KeyError:
        pass

    try:
        cwd = os.path.dirname(os.path.abspath(init_file))
        fn = os.path.join(cwd, 'VERSION')
        with open(fn) as f:
            version = f.read().strip()
        return version
    except IOError:
        pass

    from subprocess import Popen, PIPE, STDOUT
    import re

    # accept version to be coded with 2 or 3 parts (X.Y or X.Y.Z),
    # no matter the number of digits for X, Y and Z
    VERSION_MATCH = re.compile(r'(\d+\.\d+(\.\d+)?(\w|-)*)')

    try:
        p = Popen(['git', 'describe', '--tags', '--always'],
                  stdout=PIPE, stderr=STDOUT, cwd=cwd)
        out = p.communicate()[0]

        if (not p.returncode) and out:
            if not isinstance(out, str):
                out = out.decode(sys.stdout.encoding)
            v = VERSION_MATCH.search(out)
            if v is not None:
                return v.group(1)
    except OSError:
        pass
    return "999.0-version-not-found"


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
            npm_bin = check_output("npm bin").strip()
            assert npm_version != "", "need nodejs and npm installed in current PATH"
            assert LooseVersion(npm_version) >= LooseVersion(
                "1.4"), "npm < 1.4 (%s)" % (npm_version)

            commands = []

            # if we find yarn, then we use it as it is much faster
            if yarn_version != "":
                commands.append(['yarn', 'install'])
            else:
                commands.append(['npm', 'install'])

            if os.path.exists("gulpfile.js"):
                commands.append([os.path.join(npm_bin, "gulp"), 'prod', '--notests'])
            elif os.path.exists("webpack.config.js"):
                commands.append([os.path.join(npm_bin, "webpack"), '-p'])

            if os.name == 'nt':
                shell = True
            else:
                shell = False

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
        setuptools.command.build_py.build_py.run(self)


class EggInfoCommand(setuptools.command.egg_info.egg_info):
    """Custom egginfo command."""

    def run(self):
        self.run_command('build_js')
        setuptools.command.egg_info.egg_info.run(self)

def setup_www_plugin(**kw):
    package = kw['packages'][0]
    if 'version' not in kw:
        kw['version'] = getVersion(os.path.join(package, "__init__.py"))

    setup(cmdclass=dict(
        egg_info=EggInfoCommand,
        build_py=BuildPyCommand,
        build_js=BuildJsCommand),
        **kw)
