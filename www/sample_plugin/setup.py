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

import json
import os
import setuptools.command.develop
import setuptools.command.install
import setuptools.command.sdist
import subprocess

from distutils.core import Command
from setuptools import setup

# This script can run either in a source checkout (e.g., to 'setup.py sdist')
# or in an sdist tarball (to install)
MODE = 'SRC' if os.path.isdir('src') else 'SDIST'

version = "0.1.0"

base_json = {
    "name": "buildbot-sample-plugin",
    "version": version,
    "author": {
        "name": "Buildbot Team Members",
        "url": "https://github.com/buildbot"
    },
    "description": "Buildbot Sample Plugin",
    "repository": {
        "type": "git",
        "url": "https://github.com/buildbot/buildbot"
    }
}
package_json = {
    "dependencies": {
        "bower": "~1.3.3",
        "grunt": "~0.4.4",
        "grunt-newer": "~0.5.4",
        "grunt-contrib-less": "~0.11.0",
        "grunt-contrib-copy": "~0.5.0",
        "grunt-karma": "~0.8.3",
        "grunt-ngmin": "~0.0.3",
        "grunt-cli": "~0.1.13",
        "grunt-contrib-watch": "~0.6.1",
        "grunt-contrib-uglify": "~0.4.0",
        "grunt-angular-templates": "~0.5.4",
        "grunt-contrib-clean": "~0.5.0",
        "grunt-contrib-jade": "~0.11.0",
        "grunt-contrib-imagemin": "~0.6.1",
        "grunt-contrib-coffee": "~0.10.1",
        "grunt-requiregen": "~0.1.0",
        "grunt-concurrent": "~0.5.0",
        "load-grunt-tasks": "~0.4.0",
        "karma-jasmine": "~0.2.2",
        "karma-requirejs": "~0.2.1",
        "karma-coffee-preprocessor": "~0.2.1",
        "karma-phantomjs-launcher": "~0.1.4",
        "karma-chrome-launcher": "~0.1.3"
    },
    "engines": {
        "node": ">=0.10.0",
        "npm": ">=1.4.0"
    }
}
package_json.update(base_json)

# we take latest angular version until we are stable
# in a crazy CI fashion
bower_json = {
    "dependencies": {
        "angular": "latest",
        "d3": "~3.3.13"
    },
    "devDependencies": {
        "requirejs": "~2.1.5",
        "angular-mocks": "latest"
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
        json.dump(package_json, open("package.json", "w"))
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
        json.dump(bower_json, open("bower.json", "w"))
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
        for command in self.get_sub_commands():
            self.run_command(command)
        setuptools.command.develop.develop.run(self)

cmdclass['develop'] = develop

setup(
    name='buildbot-sample-plugin',
    version=version,
    description='Buildbot Sample Plugin',
    author=u'Pierre Tardy',
    author_email=u'tardyp@gmail.com',
    url='http://buildbot.net/',
    license='GNU GPL',
    py_modules=['buildbot_sample_plugin'],
    cmdclass=cmdclass,
    entry_points="""
        [buildbot.www]
        sample_plugin = buildbot_sample_plugin:ep
    """,
)
