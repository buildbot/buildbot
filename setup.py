#! /usr/bin/python

import sys
from distutils.core import setup
from buildbot import version

# Path: twisted!cvstoys!buildbot
from distutils.command.install_data import install_data
class install_data_twisted(install_data):
    """make sure data files are installed in package.
    this is evil.
    copied from Twisted/setup.py.
    """
    def finalize_options(self):
        self.set_undefined_options('install',
            ('install_lib', 'install_dir')
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

setup(name="buildbot",
      version=version,
      description="BuildBot build automation system",
      long_description=long_description,
      author="Brian Warner",
      author_email="warner-buildbot@lothar.com",
      url="http://buildbot.sourceforge.net/",
      license="GNU GPL",
      packages=["buildbot",
                "buildbot.status",
                "buildbot.changes",
                "buildbot.process",
                "buildbot.clients",
                "buildbot.slave",
                "buildbot.scripts",
                "buildbot.test"],
      data_files=[("buildbot", ["buildbot/buildbot.png"]),
                  ("buildbot/clients", ["buildbot/clients/debug.glade"]),
                  ("buildbot/status", ["buildbot/status/classic.css"]),
                  ("buildbot/scripts", ["buildbot/scripts/sample.cfg"]),],
      scripts = scripts,
      cmdclass={'install_data': install_data_twisted},
      )

# Local Variables:
# fill-column: 71
# End:
