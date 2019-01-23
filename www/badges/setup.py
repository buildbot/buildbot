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

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

try:
    from buildbot_pkg import setup_www_plugin
except ImportError:
    import sys
    print('Please install buildbot_pkg module in order to install that '
          'package, or use the pre-build .whl modules available on pypi',
          file=sys.stderr)
    sys.exit(1)

setup_www_plugin(
    name='buildbot-badges',
    description='Buildbot badges',
    author=u'Buildbot Team Members',
    author_email=u'users@buildbot.net',
    url='http://buildbot.net/',
    license='GNU GPL',
    packages=['buildbot_badges'],
    install_requires=[
        'klein',
        'CairoSVG',
        'cairocffi', 'Jinja2'
    ],
    package_data={
        '': [
            # dist is required by buildbot_pkg
            'VERSION', 'templates/*.svg.j2', 'static/.placeholder'
        ],
    },
    entry_points="""
        [buildbot.www]
        badges = buildbot_badges:ep
    """,
)
