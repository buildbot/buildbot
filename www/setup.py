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

"""
Standard setup script.
"""

from distutils.core import setup


setup_args = {
    'name': "www",
    'description': "Katana frontend",
    'long_description': "JavaScript frontend for katana",
    'package_dir': {'www': ''},
    'packages': ["www"],
    # This makes it include all files from MANIFEST.in
    # It also needs a newer version of setuptools than 17.1
    # which has a bug when dealing with MANIFEST.in
    'include_package_data': True
}

setup(**setup_args)

# Local Variables:
# fill-column: 71
# End:
