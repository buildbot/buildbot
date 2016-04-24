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
import subprocess
# XXX(sa2ajj): this is an interesting mix of distutils and setuptools.  Needs
# to be reviewed.
from distutils.command.build import build
from distutils.version import LooseVersion

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.egg_info import egg_info


def check_output(cmd):
    popen = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE)
    return popen.communicate()[0].strip()


def getVersion(init_file):
    try:
        return os.environ['BUILDBOT_VERSION']
    except KeyError:
        pass

    try:
        cwd = os.path.dirname(os.path.abspath(init_file))
        fn = os.path.join(cwd, 'VERSION')
        version = open(fn).read().strip()
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

js_built = False


def build_js(cmd):
    global js_built
    if js_built:
        return
    package = cmd.distribution.packages[0]
    if os.path.exists("gulpfile.js"):
        npm_version = check_output("npm -v")
        npm_bin = check_output("npm bin").strip()
        assert npm_version != "", "need nodejs and npm installed in current PATH"
        assert LooseVersion(npm_version) >= LooseVersion(
            "1.4"), "npm < 1.4 (%s)" % (npm_version)
        npm_cmd = ['npm', 'install']
        gulp_cmd = [os.path.join(npm_bin, "gulp"), 'prod', '--notests']
        if os.name == 'nt':
            subprocess.call(npm_cmd, shell=True)
            subprocess.call(gulp_cmd, shell=True)
        else:
            cmd.spawn(npm_cmd)
            cmd.spawn(gulp_cmd)

    cmd.copy_tree(os.path.join(package, 'static'), os.path.join(
        "build", "lib", package, "static"))

    with open(os.path.join("build", "lib", package, "VERSION"), "w") as f:
        f.write(cmd.distribution.metadata.version)

    with open(os.path.join(package, "VERSION"), "w") as f:
        f.write(cmd.distribution.metadata.version)

    js_built = True


class my_build(build):

    def run(self):
        build_js(self)
        return build.run(self)


class my_egg_info(egg_info):

    def run(self):
        build_js(self)
        return egg_info.run(self)


# XXX(sa2ajj): this class exists only to address https://bitbucket.org/pypa/setuptools/issue/261
# Once that's fixed, this class should go.
class my_build_py(build_py):

    def find_data_files(self, package, src_dir):
        tempo = build_py.find_data_files(self, package, src_dir)

        return [x for x in tempo if os.path.isfile(x)]


def setup_www_plugin(**kw):
    package = kw['packages'][0]
    if 'version' not in kw:
        kw['version'] = getVersion(os.path.join(package, "__init__.py"))
    setup(cmdclass=dict(build=my_build,
                        egg_info=my_egg_info,
                        build_py=my_build_py),
          **kw)
