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
import subprocess
from setuptools import setup
import setuptools.command.sdist
import setuptools.command.install
from distutils.core import Command

# This script can run either in a source checkout (e.g., to 'setup.py sdist')
# or in an sdist tarball (to install)
MODE = 'SRC' if os.path.isdir('src') else 'SDIST'

if MODE == 'SRC':
    # if we're in a source tree, use master's __init__ to determine the
    # version, and update the version file as a by-product
    master_init = os.path.abspath("../master/buildbot/__init__.py")
    globals = { "__file__" :  master_init }
    execfile(master_init, globals)
    version = globals['version']
    open('VERSION', 'w').write(version + '\n')
else:
    # otherwise, use what the build left us
    version = open('VERSION').read().strip()

package_json = """\
{
    "name": "buildbot-www",
    "version": "VERSION",
    "author": {
        "name": "Pierre Tardy",
        "email": "tardyp@gmail.com",
        "url": "https://github.com/tardyp"
    },
    "description": "Buildbot UI",
    "contributors": [
        {
        "name": "David Bochenski",
        "email": "david@bochenski.co.uk",
        "url": "https://github.com/Bochenski"
        },
        {
        "name": "Cary Landholt",
        "email": "cary@landholt.com",
        "url": "https://github.com/CaryLandholt"
        }
    ],
    "repository": {
        "type": "git",
        "url": "https://github.com/buildbot/buildbot"
    },
    "dependencies": {
        "grunt": "~0.3.17",
        "grunt-hustler": "~0.7.4",
        "grunt-reload": "~0.2.0",
        "grunt-jade": "~0.3.9"
    },
    "devDependencies": {
        "coffee-script": "~1.4.0",
        "testacular": "~0.5.5"
    },
    "engines": {
        "node": "0.8.x",
        "npm": "1.1.x"
    }
}
""".replace('VERSION', version)

## command classes

cmdclass = {}
class npm_install(Command):
    """
    Run 'npm install' to install all of the relevant npm modules
    """

    user_options = []

    def initialize_options(self):
        pass

    def finalize_options(self):
        pass

    def run(self):
        open("package.json", "w").write(package_json)
        self.spawn(['npm', 'install'])

cmdclass['npm_install'] = npm_install


class grunt(Command):
    """
    Run grunt to update buildbot_www/
    """

    user_options = [
        ('devel', 'd',
         "Do not minify JS")
        ]

    sub_commands = [
        ('npm_install', None)
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
    entry_points="""
        [buildbot.www]
        base = buildbot_www:ep
    """,
)
