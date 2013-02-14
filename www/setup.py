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

import os, sys
from setuptools import setup

# this script executes in a few contexts:
#
# 'SRC'     - from a new git working directory (python setup.py develop)
# 'BUILT'   - from build.sh in a git working directory, after the build
# 'SDIST'   - from an sdist tarball during installation
#
# distinguish these by which directories exist: src only, both, and built only,
# respectively

src_exists = os.path.isdir('src')
built_exists = os.path.isdir('built')
if src_exists:
    if not built_exists:
        context = 'SRC'
    else:
        context = 'BUILT'
else:
    context = 'SDIST'

def make_data_files():
    # hack to build the app automatically on setup.py develop
    if src_exists:
        if os.system("npm install"):
            raise Exception("to setup this app, you need node and npm installed in your system")
        grunt_target = "prod"
        if "develop" in sys.argv:
            grunt_target="default"
        os.system("./node_modules/.bin/grunt "+grunt_target)

# use the list of data files build.sh created, and generate filenames
    # to end up under "{sys.prefix}/share/buildbot"
    by_dir = {}
    for root, dirs, files in os.walk('built'):
        for name in files:
            fn = os.path.join(root, name)
            dirname = os.path.join('share', 'buildbot', os.path.dirname(fn))
            dirlist = by_dir.setdefault(dirname, [])
            dirlist.append(fn)
    print by_dir
    return by_dir.items()

def get_version():
    if context in ('SRC', 'BUILT'):
        # if we're in a source tree, use master's __init__ to determine the
        # version
        master_init = os.path.abspath("../master/buildbot/__init__.py")
        globals = { "__file__" :  master_init }
        execfile(master_init, globals)
        return globals['version']
    else:
        # otherwise, use what build.sh left us
        return open('built/buildbot-version.txt').read().strip()

setup(name='buildbot-www',
    version=get_version(),
    description='Buildbot UI',
    author=u'Pierre Tardy',
    author_email=u'tardyp@gmail.com',
    url='http://buildbot.net/',
    license='GNU GPL',
    py_modules=['buildbot_www'],
    data_files=make_data_files(),
    entry_points="""
        [buildbot.www]
        base = buildbot_www:ep
    """,
)
