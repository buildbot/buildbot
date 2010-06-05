#!/usr/bin/env python
#
# This software may be freely redistributed under the terms of the GNU
# general public license.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
"""
Standard setup script.
"""

import sys
import os
from distutils.core import setup

from buildslave import version

# TODO: slave script
scripts = ["bin/buildbot"]
if sys.platform == "win32":
    scripts.append("contrib/windows/buildbot.bat")
    scripts.append("contrib/windows/buildbot_service.py")

setup_args = {
    'name': "buildslave",
    'version': version,
    'description': "BuildBot Slave Daemon",
    'long_description': "See the 'buildbot' project for details",
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
        "buildslave",
        "buildslave.commands",
        "buildslave.test",
        "buildslave.test.unit",
    ],
    'scripts': scripts,
    }

try:
    # If setuptools is installed, then we'll add setuptools-specific arguments
    # to the setup args.
    import setuptools #@UnusedImport
except ImportError:
    pass
else:
    ## dependencies
    setup_args['install_requires'] = [
        'twisted >= 2.0.0',
    ]
    entry_points={
        'console_scripts': [
            # TODO: conflicts with master
            'buildbot = buildbot.scripts.runner:run'],
        },

setup(**setup_args)
