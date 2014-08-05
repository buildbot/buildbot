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

from distutils.core import Command
from setuptools import setup

# This script can run either in a source checkout (e.g., to 'setup.py sdist')
# or in an sdist tarball (to install)
MODE = 'SRC' if os.path.isdir('src') else 'SDIST'

version = "0.1.0"

# command classes

cmdclass = {}


class buildjs(Command):
    descripion = "Run everything needed to build frontend"

    def initialize_options(self):
        self.bindir = None

    def finalize_options(self):
        pass

    def get_bindir(self):
        if not self.bindir:
            p = subprocess.Popen(["npm", "bin"], stdout=subprocess.PIPE)
            self.bindir = p.communicate()[0].strip()
        return self.bindir

    def run(self):
        # bail out if we're not in SRC mode, since buildjs won't work from
        # an sdist tarball
        if MODE != 'SRC':
            return

        os.environ['PATH'] = os.environ['PATH'] + ":" + self.get_bindir()
        self.spawn(['npm', 'install'])
        self.spawn(['bower', 'install'])
        self.spawn(['gulp', 'prod'])

cmdclass['buildjs'] = buildjs


class install_www(Command):

    description = "install WWW files"

    def run(self):
        cmd = self.get_finalized_command('install')
        self.install_dir = os.path.join(cmd.install_lib, 'buildbot_www')
        out = self.copy_tree('buildbot_www', self.install_dir)
        self.outfiles.extend(out)
        (out, _) = self.copy_file('VERSION', self.install_dir)
        self.outfiles.append(out)

    def get_outputs(self):
        return self.outfiles

cmdclass['install_www'] = install_www


class sdist(setuptools.command.sdist.sdist):

    """
    Customize sdist to run buildjs first
    """

    def run(self):
        if MODE == 'SRC':
            self.run_command('buildjs')
        setuptools.command.sdist.sdist.run(self)

cmdclass['sdist'] = sdist


class install(setuptools.command.install.install):

    """
    Customize install to run buildjs first, and to run install_js after.
    """

    sub_commands = setuptools.command.install.install.sub_commands + [
        ('install_www', None)
    ]

    def run(self):
        if MODE == 'SRC':
            self.run_command('buildjs')
        setuptools.command.install.install.run(self)

cmdclass['install'] = install


class develop(setuptools.command.develop.develop):

    """
    Customize develop to run npm/bower install.
    """

    def run(self):
        if MODE == 'SRC':
            self.run_command('buildjs')
        setuptools.command.develop.develop.run(self)

cmdclass['develop'] = develop

setup(
    name='buildbot-codeparameter',
    version=version,
    description='Buildbot Sample Plugin',
    author=u'Pierre Tardy',
    author_email=u'tardyp@gmail.com',
    url='http://buildbot.net/',
    license='GNU GPL',
    py_modules=['buildbot_codeparameter'],
    cmdclass=cmdclass,
    entry_points="""
        [buildbot.www]
        codeparameter = buildbot_codeparameter:ep
    """,
)
