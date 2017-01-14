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
    import mock  # noqa
    import buildbot  # noqa
except ImportError:
    import sys
    print("Please install buildbot, buildbot_pkg, and mock modules in order to install that package, or use the pre-build .whl modules available on pypi", file=sys.stderr)
    sys.exit(1)

setup_www_plugin(
    name='buildbot-www',
    description='Buildbot UI',
    author=u'Pierre Tardy',
    author_email=u'tardyp@gmail.com',
    setup_requires=['buildbot', 'buildbot_pkg', 'mock'],
    url='http://buildbot.net/',
    license='GNU GPL',
    packages=['buildbot_www'],
    package_data={
        '': [
            'VERSION',
            'static/*',
            'static/img/*',
            'static/fonts/*',
        ]
    },
    entry_points="""
        [buildbot.www]
        base = buildbot_www:ep
    """
)
