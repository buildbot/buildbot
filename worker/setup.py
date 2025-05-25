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

import os
import sys

from setuptools import Command
from setuptools import setup
from setuptools.command.sdist import sdist

from buildbot_worker import version

BUILDING_WHEEL = bool("bdist_wheel" in sys.argv)


class our_install_data(Command):
    def initialize_options(self):
        self.install_dir = None

    def finalize_options(self):
        self.set_undefined_options(
            'install',
            ('install_lib', 'install_dir'),
        )

    def run(self):
        # ensure there's a buildbot_worker/VERSION file
        fn = os.path.join(self.install_dir, 'buildbot_worker', 'VERSION')
        with open(fn, 'w') as f:
            f.write(version)


class our_sdist(sdist):
    def make_release_tree(self, base_dir, files):
        sdist.make_release_tree(self, base_dir, files)
        # ensure there's a buildbot_worker/VERSION file
        fn = os.path.join(base_dir, 'buildbot_worker', 'VERSION')
        open(fn, 'w').write(version)

        # ensure that NEWS has a copy of the latest release notes, copied from
        # the master tree, with the proper version substituted
        src_fn = os.path.join('..', 'master', 'docs', 'relnotes/index.rst')
        with open(src_fn) as f:
            src = f.read()
        src = src.replace('|version|', version)
        dst_fn = os.path.join(base_dir, 'NEWS')
        with open(dst_fn, 'w') as f:
            f.write(src)


setup_args = {
    'version': version,
    'packages': [
        "buildbot_worker",
        "buildbot_worker.util",
        "buildbot_worker.commands",
        "buildbot_worker.scripts",
        "buildbot_worker.monkeypatches",
    ]
    + (
        []
        if BUILDING_WHEEL
        else [  # skip tests for wheels (save 40% of the archive)
            "buildbot_worker.test",
            "buildbot_worker.test.fake",
            "buildbot_worker.test.unit",
            "buildbot_worker.test.util",
        ]
    ),
    # mention data_files, even if empty, so install_data is called and
    # VERSION gets copied
    'data_files': [("buildbot_worker", [])],
    'package_data': {
        '': [
            'VERSION',
        ],
        'buildbot_worker': [
            'py.typed',
        ],
    },
    'cmdclass': {'install_data': our_install_data, 'sdist': our_sdist},
    'entry_points': {
        'console_scripts': [
            'buildbot-worker=buildbot_worker.scripts.runner:run',
            # this will also be shipped on non windows :-(
            'buildbot_worker_windows_service=buildbot_worker.scripts.windows_service:HandleCommandLine',
        ]
    },
}

# set zip_safe to false to force Windows installs to always unpack eggs
# into directories, which seems to work better --
# see http://buildbot.net/trac/ticket/907
if sys.platform == "win32":
    setup_args['zip_safe'] = False

twisted_ver = ">= 21.2.0"

setup_args['install_requires'] = [
    'twisted ' + twisted_ver,
    'autobahn >= 0.16.0',
    'msgpack >= 0.6.0',
    # buildbot_worker_windows_service needs pywin32
    'pywin32; platform_system=="Windows"',
]

# Unit test hard dependencies.
test_deps = [
    'psutil',
]

setup_args['extras_require'] = {
    'test': test_deps,
}

if os.getenv('NO_INSTALL_REQS'):
    setup_args['install_requires'] = None
    setup_args['extras_require'] = None

setup(**setup_args)
