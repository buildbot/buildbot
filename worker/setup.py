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

from __future__ import absolute_import
from __future__ import print_function

import os
import sys

from buildbot_worker import version

try:
    # If setuptools is installed, then we'll add setuptools-specific arguments
    # to the setup args.
    import setuptools
    from setuptools import setup
    from setuptools.command.sdist import sdist
except ImportError:
    setuptools = None
    from distutils.command.sdist import sdist
    from distutils.core import setup


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
    'name': "buildbot-worker",
    'version': version,
    'description': "Buildbot Worker Daemon",
    'long_description': "See the 'buildbot' package for details",
    'author': "Brian Warner",
    'author_email': "warner-buildbot@lothar.com",
    'maintainer': "Dustin J. Mitchell",
    'maintainer_email': "dustin@v.igoro.us",
    'url': "http://buildbot.net/",
    'classifiers': [
        'Development Status :: 5 - Production/Stable',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Software Development :: Testing',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ],

    'packages': [
        "buildbot_worker",
        "buildbot_worker.util",
        "buildbot_worker.backports",
        "buildbot_worker.commands",
        "buildbot_worker.scripts",
        "buildbot_worker.monkeypatches",
        "buildbot_worker.test",
        "buildbot_worker.test.fake",
        "buildbot_worker.test.unit",
        "buildbot_worker.test.util",
    ],
    'package_data': {
        '': [
            'VERSION',
        ]
    },
    'cmdclass': {
        'sdist': our_sdist
    },
    'entry_points': {
        'console_scripts': [
            'buildbot-worker=buildbot_worker.scripts.runner:run',
            # this will also be shipped on non windows :-(
            'buildbot_worker_windows_service=buildbot_worker.scripts.windows_service:HandleCommandLine',  # noqa pylint: disable=line-too-long
        ]}
}

# set zip_safe to false to force Windows installs to always unpack eggs
# into directories, which seems to work better --
# see http://buildbot.net/trac/ticket/907
if sys.platform == "win32":
    setup_args['zip_safe'] = False

twisted_ver = ">= 17.9.0"

if setuptools is not None:
    setup_args['install_requires'] = [
        'twisted ' + twisted_ver,
        'future',
    ]

    # Unit test hard dependencies.
    test_deps = [
        'mock',
    ]

    setup_args['tests_require'] = test_deps

    setup_args['extras_require'] = {
        'test': [
            'pep8',
            # spellcheck introduced in version 1.4.0
            'pylint>=1.4.0',
            'pyenchant',
            'flake8~=2.6.0',
        ] + test_deps,
    }

    if '--help-commands' in sys.argv or 'trial' in sys.argv or 'test' in sys.argv:
        setup_args['setup_requires'] = [
            'setuptools_trial',
        ]

    if os.getenv('NO_INSTALL_REQS'):
        setup_args['install_requires'] = None
        setup_args['extras_require'] = None

setup(**setup_args)
