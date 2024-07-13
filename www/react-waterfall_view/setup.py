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

import os.path

try:
    from buildbot_pkg import getVersion
    from buildbot_pkg import setup_www_plugin
except ImportError:
    import sys

    print(
        'Please install buildbot_pkg module in order to install that '
        'package, or use the pre-build .whl modules available on pypi',
        file=sys.stderr,
    )
    sys.exit(1)


PACKAGE_NAME = "buildbot_react_waterfall_view"
version = getVersion(os.path.join(PACKAGE_NAME, '__init__.py'))

setup_www_plugin(
    name='buildbot-react-waterfall-view',
    description='Buildbot Waterfall View plugin (React)',
    author='Pierre Tardy',
    author_email='tardyp@gmail.com',
    setup_requires=['buildbot_pkg'],
    version=version,
    install_requires=['buildbot', f'buildbot-waterfall-view=={version}'],
    url='http://buildbot.net/',
    packages=[PACKAGE_NAME],
    package_data={'': ['VERSION']},
    entry_points="""
        [buildbot.www]
        react_waterfall_view = buildbot_waterfall_view:ep
    """,
    classifiers=['License :: OSI Approved :: GNU General Public License v2 (GPLv2)'],
)
