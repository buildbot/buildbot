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

import sys
import os
import glob

from distutils.core import setup, Command
from buildbot import version

from distutils.command.install_data import install_data
from distutils.command.sdist import sdist

def include(d, e):
    """Generate a pair of (directory, file-list) for installation.

    'd' -- A directory
    'e' -- A glob pattern"""
    
    return (d, [f for f in glob.glob('%s/%s'%(d, e)) if os.path.isfile(f)])

class _SetupBuildCommand(Command):
    """
    Master setup build command to subclass from.
    """

    user_options = []

    def initialize_options(self):
        """
        Setup the current dir.
        """
        self._dir = os.getcwd()

    def finalize_options(self):
        """
        Required.
        """
        pass


class TestCommand(_SetupBuildCommand):
    """
    Executes tests from setup.
    """

    description = "Run unittests inline"

    def run(self):
        """
        Public run method.
        """
        self._run(os.path.normpath(os.path.abspath(
           os.path.join('buildbot', 'test'))))

    def _run(self, test_loc):
        """
        Executes the test step.

        @param test_loc: location of test module
        @type test_loc: str
        """
        from twisted.scripts.trial import run

        # remove the 'test' option from argv
        sys.argv.remove('test')

        # Mimick the trial script by adding the path as the last arg
        sys.argv.append(test_loc)

        # Add the current dir to path and pull it all together
        sys.path.insert(0, os.path.curdir)
        sys.path[:] = map(os.path.abspath, sys.path)
        # GO!
        run()


class SdistTestCommand(TestCommand):
    """
    Runs unittests from the sdist output.
    """

    description = "Run unittests from inside an sdist distribution"

    def run(self):
        """
        Interesting magic to get a source dist and running trial on it.

        NOTE: there is magic going on here! If you know a better way feel
              free to update it.
        """
        # Clean out dist/
        if os.path.exists('dist'):
            for root, dirs, files in os.walk('dist', topdown=False):
                for name in files:
                    os.remove(os.path.join(root, name))
                for name in dirs:
                    os.rmdir(os.path.join(root, name))
        # Import setup making it as if we ran setup.py with the sdist arg
        sys.argv.append('sdist')
        import setup #@Reimport @UnresolvedImport @UnusedImport
        try:
            # attempt to extract the sdist data
            from gzip import GzipFile
            from tarfile import TarFile
            # We open up the gzip as well as using the first item as the sdist
            gz = GzipFile(os.path.join('dist', os.listdir('dist')[0]))
            tf = TarFile(fileobj=gz)
            # Make the output dir and generate the extract path
            os.mkdir(os.path.join('dist', 'sdist_test'))
            ex_path = os.path.join('dist', 'sdist_test',
                tf.getmembers()[0].name, 'buildbot', 'test')
            # Extract the data and run tests
            print "Extracting to %s" % ex_path
            tf.extractall(os.path.join('dist', 'sdist_test'))
            print "Executing tests ..."
            self._run(os.path.normpath(os.path.abspath(ex_path)))
        except IndexError, ie:
            # We get called twice and the IndexError is OK
            pass


class install_data_twisted(install_data):
    """make sure data files are installed in package.
    this is evil.
    copied from Twisted/setup.py.
    """

    def finalize_options(self):
        self.set_undefined_options('install',
            ('install_lib', 'install_dir'),
        )
        install_data.finalize_options(self)

    def run(self):
        install_data.run(self)
        # ensure there's a buildbot/VERSION file
        fn = os.path.join(self.install_dir, 'buildbot', 'VERSION')
        open(fn, 'w').write(version)
        self.outfiles.append(fn)

class our_sdist(sdist):

    def make_release_tree(self, base_dir, files):
        sdist.make_release_tree(self, base_dir, files)
        # ensure there's a buildbot/VERSION file
        fn = os.path.join(base_dir, 'buildbot', 'VERSION')
        open(fn, 'w').write(version)


long_description="""
The BuildBot is a system to automate the compile/test cycle required by
most software projects to validate code changes. By automatically
rebuilding and testing the tree each time something has changed, build
problems are pinpointed quickly, before other developers are
inconvenienced by the failure. The guilty developer can be identified
and harassed without human intervention. By running the builds on a
variety of platforms, developers who do not have the facilities to test
their changes everywhere before checkin will at least know shortly
afterwards whether they have broken the build or not. Warning counts,
lint checks, image size, compile time, and other build parameters can
be tracked over time, are more visible, and are therefore easier to
improve.
"""

scripts = ["bin/buildbot"]
# sdist is usually run on a non-Windows platform, but the buildslave.bat file
# still needs to get packaged.
if 'sdist' in sys.argv or sys.platform == 'win32':
    scripts.append("contrib/windows/buildbot.bat")
    scripts.append("contrib/windows/buildbot_service.py")

setup_args = {
    'name': "buildbot",
    'version': version,
    'description': "BuildBot build automation system",
    'long_description': long_description,
    'author': "Brian Warner",
    'author_email': "warner-buildbot@lothar.com",
    'maintainer': "Dustin J. Mitchell",
    'maintainer_email': "dustin@v.igoro.us",
    'url': "http://buildbot.net/",
    'license': "GNU GPL",
    'classifiers': [
        'Development Status :: 5 - Production/Stable',
        'Environment :: No Input/Output (Daemon)',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Software Development :: Testing',
        ],

    'packages': ["buildbot",
              "buildbot.status", "buildbot.status.web","buildbot.status.web.hooks",
              "buildbot.changes",
              "buildbot.steps",
              "buildbot.steps.package",
              "buildbot.steps.package.rpm",
              "buildbot.process",
              "buildbot.clients",
              "buildbot.monkeypatches",
              "buildbot.schedulers",
              "buildbot.scripts",
              "buildbot.db",
              "buildbot.db.migrate.versions",
              "buildbot.util",
              "buildbot.test",
              "buildbot.test.fake",
              "buildbot.test.unit",
              "buildbot.test.util",
              "buildbot.test.regressions",
              ],
    'data_files': [
                ("buildbot", [
                    "buildbot/buildbot.png",
                ]),
                ("buildbot/db/migrate", [
                    "buildbot/db/migrate/migrate.cfg",
                ]),
                include("buildbot/db/migrate/versions", "*.py"),
                ("buildbot/clients", [
                    "buildbot/clients/debug.glade",
                ]),
                ("buildbot/status/web/files", [
                    "buildbot/status/web/files/default.css",
                    "buildbot/status/web/files/bg_gradient.jpg",
                    "buildbot/status/web/files/robots.txt",
                    "buildbot/status/web/files/favicon.ico",
                ]),
                include("buildbot/status/web/templates", '*.html'),
                include("buildbot/status/web/templates", '*.xml'),
                ("buildbot/scripts", [
                    "buildbot/scripts/sample.cfg",
                ]),
                ],
    'scripts': scripts,
    'cmdclass': {'install_data': install_data_twisted,
                 'test': TestCommand,
                 'sdist_test': SdistTestCommand,
                 'sdist': our_sdist},
    }

# set zip_safe to false to force Windows installs to always unpack eggs
# into directories, which seems to work better --
# see http://buildbot.net/trac/ticket/907
if sys.platform == "win32":
    setup_args['zip_safe'] = False

py_25 = sys.version_info[0] > 2 or (sys.version_info[0] == 2 and sys.version_info[1] >= 5)
py_26 = sys.version_info[0] > 2 or (sys.version_info[0] == 2 and sys.version_info[1] >= 6)

try:
    # If setuptools is installed, then we'll add setuptools-specific arguments
    # to the setup args.
    import setuptools #@UnusedImport
except ImportError:
    pass
else:
    ## dependencies
    setup_args['install_requires'] = [
        'twisted >= 8.0.0',
        'Jinja2 >= 2.1',
        'sqlalchemy >= 0.6',
        # buildbot depends on sqlalchemy internals. See buildbot.db.model.
        'sqlalchemy-migrate == 0.6',
    ]
    # Python-2.6 and up includes json
    if not py_26:
        setup_args['install_requires'].append('simplejson')

    # Python-2.6 and up includes a working A sqlite (py25's is broken)
    if not py_26:
        setup_args['install_requires'].append('pysqlite')

    if os.getenv('NO_INSTALL_REQS'):
        setup_args['install_requires'] = None

setup(**setup_args)

# Local Variables:
# fill-column: 71
# End:
