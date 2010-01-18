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
import re

from distutils.core import setup, Command
from buildbot import version

# Path: twisted!cvstoys!buildbot
from distutils.command.install_data import install_data


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

        # Mimick the trial script by adding the path as the last arg
        sys.argv.append(test_loc)

        # No superuser should execute tests
        if hasattr(os, "getuid") and os.getuid() == 0:
            raise SystemExit('Do not test as a superuser! Exiting ...')

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
        import setup
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
if sys.platform == "win32":
    scripts.append("contrib/windows/buildbot.bat")
    scripts.append("contrib/windows/buildbot_service.py")

testmsgs = []
for f in os.listdir("buildbot/test/mail"):
    if f.endswith("~"):
        continue
    if re.search(r'\.\d+$', f):
        testmsgs.append("buildbot/test/mail/%s" % f)

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
    # does this classifiers= mean that this can't be installed on 2.2/2.3?
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
              "buildbot.status", "buildbot.status.web",
              "buildbot.changes",
              "buildbot.steps",
              "buildbot.steps.package",
              "buildbot.steps.package.rpm",
              "buildbot.process",
              "buildbot.clients",
              "buildbot.slave",
              "buildbot.scripts",
              "buildbot.test",
              ],
    'data_files': [("buildbot", ["buildbot/buildbot.png"]),
                ("buildbot/clients", ["buildbot/clients/debug.glade"]),
                ("buildbot/status/web",
                 ["buildbot/status/web/classic.css",
                  "buildbot/status/web/default.css",
                  "buildbot/status/web/extended.css",
                  "buildbot/status/web/index.html",
                  "buildbot/status/web/robots.txt",
                  "buildbot/status/web/bg_gradient.jpg",
                  ]),
                ("buildbot/scripts", ["buildbot/scripts/sample.cfg"]),
                ("buildbot/test/mail", testmsgs),
                ("buildbot/test/subdir", ["buildbot/test/subdir/emit.py"]),
                ],
    'scripts': scripts,
    'cmdclass': {'install_data': install_data_twisted,
                 'test': TestCommand,
                 'sdist_test': SdistTestCommand},
    }

try:
    # If setuptools is installed, then we'll add setuptools-specific arguments
    # to the setup args.
    import setuptools
except ImportError:
    pass
else:
    setup_args['install_requires'] = ['twisted >= 2.0.0']
    entry_points={
        'console_scripts': [
            'buildbot = buildbot.scripts.runner:run'],
        },

setup(**setup_args)

# Local Variables:
# fill-column: 71
# End:
