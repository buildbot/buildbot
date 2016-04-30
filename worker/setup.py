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
from distutils.command.install_data import install_data
from distutils.command.sdist import sdist
from distutils.core import setup

from buildbot_worker import version

scripts = ["bin/buildbot-worker"]
# sdist is usually run on a non-Windows platform, but the buildbot-worker.bat
# file still needs to get packaged.
if 'sdist' in sys.argv or sys.platform == 'win32':
    scripts.append("contrib/windows/buildbot-worker.bat")
    scripts.append("contrib/windows/buildbot_service.py")


class our_install_data(install_data):

    def finalize_options(self):
        self.set_undefined_options('install',
                                   ('install_lib', 'install_dir'),
                                   )
        install_data.finalize_options(self)

    def run(self):
        install_data.run(self)
        # ensure there's a buildbot_worker/VERSION file
        fn = os.path.join(self.install_dir, 'buildbot_worker', 'VERSION')
        open(fn, 'w').write(version)
        self.outfiles.append(fn)


class our_sdist(sdist):

    def make_release_tree(self, base_dir, files):
        sdist.make_release_tree(self, base_dir, files)
        # ensure there's a buildbot_worker/VERSION file
        fn = os.path.join(base_dir, 'buildbot_worker', 'VERSION')
        open(fn, 'w').write(version)

        # ensure that NEWS has a copy of the latest release notes, copied from
        # the master tree, with the proper version substituted
        src_fn = os.path.join('..', 'master', 'docs', 'relnotes/index.rst')
        src = open(src_fn).read()
        src = src.replace('|version|', version)
        dst_fn = os.path.join(base_dir, 'NEWS')
        open(dst_fn, 'w').write(src)

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
    'license': "GNU GPL",
    'classifiers': [
        'Development Status :: 5 - Production/Stable',
        'Environment :: No Input/Output (Daemon)',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Software Development :: Testing',
    ],

    'packages': [
        "buildbot_worker",
        "buildbot_worker.commands",
        "buildbot_worker.scripts",
        "buildbot_worker.monkeypatches",
        "buildbot_worker.test",
        "buildbot_worker.test.fake",
        "buildbot_worker.test.util",
        "buildbot_worker.test.unit",
    ],
    'scripts': scripts,
    # mention data_files, even if empty, so install_data is called and
    # VERSION gets copied
    'data_files': [("buildbot_worker", [])],
    'cmdclass': {
        'install_data': our_install_data,
        'sdist': our_sdist
    }
}

# set zip_safe to false to force Windows installs to always unpack eggs
# into directories, which seems to work better --
# see http://buildbot.net/trac/ticket/907
if sys.platform == "win32":
    setup_args['zip_safe'] = False

try:
    # If setuptools is installed, then we'll add setuptools-specific arguments
    # to the setup args.
    import setuptools  # @UnusedImport
except ImportError:
    pass
else:
    setup_args['install_requires'] = [
        'twisted >= 8.0.0',
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
            'pylint==1.1.0',
            'pyflakes',
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
