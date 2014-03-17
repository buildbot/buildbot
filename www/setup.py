#!/usr/bin/env python
#
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
import setuptools.command.develop
import setuptools.command.install
import setuptools.command.sdist
import subprocess
import sys

from distutils.core import Command
from distutils.version import LooseVersion
from setuptools import setup
try:
    import simplejson as json
    assert json
except ImportError:
    try:
        import json
        assert json
    except ImportError:
        # a fresh python-2.5 environment may have neither json nor simplejson
        # luckily it's only required for building from source
        json = None


def check_output(cmd):
    return subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE).communicate()[0]

# This script can run either in a source checkout (e.g., to 'setup.py sdist')
# or in an sdist tarball (to install)
MODE = 'SRC' if os.path.isdir('src') else 'SDIST'

if MODE == 'SRC':
    # if we're in a source tree, use master's __init__ to determine the
    # version, and update the version file as a by-product
    master_init = os.path.abspath("../master/buildbot/__init__.py")
    globals = {"__file__": master_init}
    execfile(master_init, globals)
    version = globals['version']
    open('VERSION', 'w').write(version + '\n')
else:
    # otherwise, use what the build left us
    version = open('VERSION').read().strip()

base_json = {
    "name": "buildbot-www",
    "version": version,
    "author": {
        "name": "Buildbot Team Members",
        "url": "https://github.com/buildbot"
    },
    "description": "Buildbot UI",
    "repository": {
        "type": "git",
        "url": "https://github.com/buildbot/buildbot"
    }
}
package_json = {
    "dependencies": {
        "grunt": "~0.4.1",
        "grunt-cli": "~0.1.1",
        "grunt-contrib-clean": "~0.4.0",
        "grunt-contrib-coffee": "~0.7.0",
        "grunt-contrib-copy": "~0.4.1",
        "grunt-contrib-imagemin": "~0.1.3",
        "grunt-contrib-jade": "~0.5.0",
        "grunt-contrib-less": "~0.5.0",
        "grunt-contrib-concat": "~0.3.0",
        "grunt-contrib-livereload": "~0.1.2",
        "grunt-contrib-requirejs": "~0.4.0",
        "grunt-contrib-watch": "~0.5.3",
        "grunt-mkdir": "~0.1.1",
        "grunt-html2js": "~0.1.6",
        "grunt-coffeelint": "~0.0.8",
        "grunt-requiregen": "~0.1.0",
        "grunt-karma": "~0.8.0",
        "karma": "~0.12.0",
        "karma-jasmine": "~0.2.2",
        "karma-requirejs": "~0.2.1",
        "karma-coffee-preprocessor": "*",
        "karma-chrome-launcher": "*",
        "karma-firefox-launcher": "*",
        "karma-phantomjs-launcher": "*",
        "bower": "~1.2.7"
    },
    "engines": {
        "node": "0.8.x",
        "npm": "1.2.x"
    }
}
package_json.update(base_json)

ANGULAR_TAG = "1.2.14"
bower_json = {
    "dependencies": {
        "bootstrap": "~3.0.0",
        "font-awesome": "4.0.3",
        "angular": ANGULAR_TAG,
        "angular-animate": ANGULAR_TAG,
        "angular-bootstrap": "~0.10.0",
        "angular-ui-router": "0.2.9",
        "angular-recursion": "1.0.0",
        "restangular": "~1.3.1",
        "lodash": "~2.4.1",
        "underscore.string": "~2.3.3",
        "html5shiv": "~3.6.2",
        "jquery": "~2.1.0",
        "requirejs": "~2.1.5",
        "moment": "~2.1.0",
        # test deps
        "angular-mocks": ANGULAR_TAG
    }
}

bower_json.update(base_json)

# command classes

cmdclass = {}


class npm_install(Command):
    description = "Run 'npm install' to install all of the relevant npm modules"

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        assert json, "Install 'json' or 'simplejson' first"
        json.dump(package_json, open("package.json", "w"))
        npm_version = check_output("npm -v").strip()
        assert npm_version != "", "need nodejs and npm installed in current PATH"
        assert LooseVersion(npm_version) >= LooseVersion("1.2"), "npm < 1.2 (%s)" % (npm_version)
        self.spawn(['npm', 'install'])

cmdclass['npm_install'] = npm_install


class bower_install(npm_install):
    description = "Run 'bower install' to install all of the relevant bower modules"

    sub_commands = [
        ('npm_install', None)
    ]

    def run(self):
        for command in self.get_sub_commands():
            self.run_command(command)
        assert json, "Install 'json' or 'simplejson' first"
        json.dump(bower_json, open("bower.json", "w"))
        self.spawn(['rm', '-rf', 'bower_components'])
        self.spawn(['./node_modules/.bin/bower', 'install'])

cmdclass['bower_install'] = bower_install


class grunt(Command):
    descripion = "Run grunt to update buildbot_www/"

    user_options = [
        ('devel', 'd',
         "Do not minify JS")
    ]

    sub_commands = [
        ('bower_install', None)
    ]

    def initialize_options(self):
        self.devel = False
        self.bindir = None

    def finalize_options(self):
        pass

    def get_bindir(self):
        if not self.bindir:
            p = subprocess.Popen(["npm", "bin"], stdout=subprocess.PIPE)
            self.bindir = p.communicate()[0].strip()
        return self.bindir

    def run(self):
        # bail out if we're not in SRC mode, since grunt won't work from
        # an sdist tarball
        if MODE != 'SRC':
            return

        for command in self.get_sub_commands():
            self.run_command(command)

        args = ['default'] if self.devel else ['prod']
        bindir = self.get_bindir()
        self.spawn([os.path.abspath(os.path.join(bindir, 'grunt'))] + args)

cmdclass['grunt'] = grunt


class install_www(Command):

    description = "install WWW files"

    user_options = [
        ('install-dir=', 'd',
         "base directory for installing WWW files "
         "(default: `$install_lib/buildbot_www`)"),
    ]

    boolean_options = ['force']

    def initialize_options(self):
        self.install_dir = None
        self.outfiles = []

    def finalize_options(self):
        if not self.install_dir:
            cmd = self.get_finalized_command('install')
            self.install_dir = os.path.join(cmd.install_lib, 'buildbot_www')

    def run(self):
        out = self.copy_tree('buildbot_www', self.install_dir)
        self.outfiles.extend(out)
        (out, _) = self.copy_file('VERSION', self.install_dir)
        self.outfiles.append(out)

    def get_outputs(self):
        return self.outfiles

cmdclass['install_www'] = install_www


class sdist(setuptools.command.sdist.sdist):

    """
    Customize sdist to run grunt first
    """

    def run(self):
        if MODE == 'SRC':
            self.run_command('grunt')
        setuptools.command.sdist.sdist.run(self)

cmdclass['sdist'] = sdist


class install(setuptools.command.install.install):

    """
    Customize install to run grunt first, and to run install_js after.
    """

    sub_commands = setuptools.command.install.install.sub_commands + [
        ('install_www', None)
    ]

    def run(self):
        if MODE == 'SRC':
            self.run_command('grunt')
        setuptools.command.install.install.run(self)

cmdclass['install'] = install


class develop(setuptools.command.develop.develop):

    """
    Customize develop to run npm/bower install.
    """

    sub_commands = setuptools.command.develop.develop.sub_commands + [
        ('bower_install', None),
        ('grunt', None)
    ]

    def run(self):
        if MODE == 'SRC':
            for command in self.get_sub_commands():
                self.run_command(command)
        setuptools.command.develop.develop.run(self)

cmdclass['develop'] = develop

py_26 = (sys.version_info[0] > 2 or
         (sys.version_info[0] == 2 and sys.version_info[1] >= 6))

install_requires = []
if not py_26:
    install_requires.append('simplejson')  # for setup.py itself, actually

setup(
    name='buildbot-www',
    version=version,
    description='Buildbot UI',
    author=u'Pierre Tardy',
    author_email=u'tardyp@gmail.com',
    url='http://buildbot.net/',
    license='GNU GPL',
    py_modules=['buildbot_www'],
    cmdclass=cmdclass,
    install_requires=install_requires,
    entry_points="""
        [buildbot.www]
        base = buildbot_www:ep
    """,
)
