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

try:
    from buildbot_pkg import setup_www_plugin
except ImportError:
    import sys
    print('Please install buildbot_pkg module in order to install that '
          'package, or use the pre-build .whl modules available on pypi',
          file=sys.stderr)
    sys.exit(1)

setup_www_plugin(
    name='buildbot-www-react',
    description='Buildbot UI (React)',
    author='Povilas Kanapickas',
    author_email='povilas@radix.lt',
    setup_requires=['buildbot_pkg'],
    install_requires=['buildbot'],
    url='http://buildbot.net/',
    packages=['buildbot_www_react'],
    package_data={
        '': [
            'VERSION',
            'static/*',
            'static/js/*',
            'static/css/*',
            'static/img/*',
            'static/fonts/*',
        ]
    },
    entry_points="""
        [buildbot.www]
        base_react = buildbot_www_react:ep
    """,
    classifiers=[
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)'
    ],
)
