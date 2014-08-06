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

from setuptools import setup

# For now, we only support develop, and manual npm install
# plan is to use wheel for binary distribution: http://wheel.readthedocs.org/en/latest/

MODE = 'SRC' if os.path.isdir('src') else 'SDIST'

if MODE == 'SRC':
    # if we're in a source tree, use master's __init__ to determine the
    # version, and update the version file as a by-product
    master_init = os.path.abspath("../../master/buildbot/__init__.py")
    globals = {"__file__": master_init}
    execfile(master_init, globals)
    version = globals['version']
    open('VERSION', 'w').write(version + '\n')
else:
    # otherwise, use what the build left us
    version = open('VERSION').read().strip()


setup(
    name='buildbot-console-view',
    version=version,
    description='Buildbot Console View plugin.',
    author=u'Pierre Tardy',
    author_email=u'tardyp@gmail.com',
    url='http://buildbot.net/',
    license='GNU GPL',
    py_modules=['buildbot_www'],
    entry_points="""
        [buildbot.www]
        base = buildbot_www:ep
    """,
)
