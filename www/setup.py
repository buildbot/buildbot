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

def make_data_files():
    by_dir = {}
    for fn in open('built/file-list.txt'):
        fn = fn.strip()
        dirname = os.path.join('share', 'buildbot', os.path.dirname(fn))
        dirlist = by_dir.setdefault(dirname, [])
        dirlist.append(fn)
    return by_dir.items()

setup(name='buildbot-www',
    version=open('built/buildbot-version.txt').read().strip(),
    description='Buildbot JavaScript UI',
    author=u'Pierre Tardy',
    author_email=u'tardyp@gmail.com',
    url='http://buildbot.net/',
    license='GNU GPL',
    py_modules=['buildbot_www'],
    data_files=make_data_files(),
    entry_points="""
        [buildbot.www]
        base = buildbot_www
    """,
)
