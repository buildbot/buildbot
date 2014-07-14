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

import glob
import os
import sys

from buildbot import version
from distutils.core import setup

from distutils.command.install_data import install_data
from distutils.command.sdist import sdist


def include(d, e):
    """Generate a pair of (directory, file-list) for installation.

    'd' -- A directory
    'e' -- A glob pattern"""

    return (d, [f for f in glob.glob('%s/%s' % (d, e)) if os.path.isfile(f)])


def include_statics(d):
    r = []
    for root, ds, fs in os.walk(d):
        r.append((root, [os.path.join(root, f) for f in fs]))
    return r


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

        # ensure that NEWS has a copy of the latest release notes, with the
        # proper version substituted
        src_fn = os.path.join('docs', 'relnotes/index.rst')
        src = open(src_fn).read()
        src = src.replace('|version|', version)
        dst_fn = os.path.join(base_dir, 'NEWS')
        open(dst_fn, 'w').write(src)


def define_plugin_entry(name, module_name):
    """
    helper to produce lines suitable for setup.py's entry_points
    """
    if isinstance(name, tuple):
        entry, name = name
    else:
        entry = name
    return '%s = %s:%s' % (entry, module_name, name)


def define_plugin_entries(groups):
    """
    helper to all groups for plugins
    """
    result = dict()

    for group, modules in groups:
        tempo = []
        for module_name, names in modules:
            tempo.extend([define_plugin_entry(name, module_name)
                          for name in names])
        result[group] = tempo

    return result


long_description = """
The Buildbot is a system to automate the compile/test cycle required by
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
    'description': "The Continuous Integration Framework",
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
                 "buildbot.status",
                 "buildbot.www",
                 "buildbot.changes",
                 "buildbot.buildslave",
                 "buildbot.buildslave.protocols",
                 "buildbot.steps",
                 "buildbot.steps.package",
                 "buildbot.steps.package.deb",
                 "buildbot.steps.package.rpm",
                 "buildbot.steps.source",
                 "buildbot.process",
                 "buildbot.process.users",
                 "buildbot.clients",
                 "buildbot.monkeypatches",
                 "buildbot.schedulers",
                 "buildbot.scripts",
                 "buildbot.db",
                 "buildbot.db.types",
                 "buildbot.db.migrate.versions",
                 "buildbot.mq",
                 "buildbot.data",
                 "buildbot.test",
                 "buildbot.test.fake",
                 "buildbot.test.fuzz",
                 "buildbot.test.integration",
                 "buildbot.test.regressions",
                 "buildbot.test.unit",
                 "buildbot.test.util",
                 "buildbot.util",
                 ],
    'data_files': [
        ("buildbot", [
            "buildbot/buildbot.png",
        ]),
        ("buildbot/db/migrate", [
            "buildbot/db/migrate/migrate.cfg",
        ]),
        include("buildbot/db/migrate/versions", "*.py"),
        ("buildbot/scripts", [
            "buildbot/scripts/sample.cfg",
            "buildbot/scripts/buildbot_tac.tmpl",
        ]),
    ] + include_statics("buildbot/www/static"),
    'scripts': scripts,
    'cmdclass': {'install_data': install_data_twisted,
                 'sdist': our_sdist},
    'entry_points': define_plugin_entries([
        ('buildbot.change_source', [
            ('buildbot.changes.mail', [
                'MaildirSource', 'CVSMaildirSource',
                'SVNCommitEmailMaildirSource',
                'BzrLaunchpadEmailMaildirSource']),
            ('buildbot.changes.bitbucket', ['BitbucketPullrequestPoller']),
            ('buildbot.changes.bonsaipoller', ['BonsaiPoller']),
            ('buildbot.changes.gerritchangesource', ['GerritChangeSource']),
            ('buildbot.changes.gitpoller', ['GitPoller']),
            ('buildbot.changes.hgpoller', ['HgPoller']),
            ('buildbot.changes.p4poller', ['P4Source']),
            ('buildbot.changes.pb', ['PBChangeSource']),
            ('buildbot.changes.svnpoller', ['SVNPoller'])
        ]),
        ('buildbot.scheduler', [
            ('buildbot.schedulers.basic', [
                'SingleBranchScheduler', 'AnyBranchScheduler', 'Triggerable']),
            ('buildbot.schedulers.dependent', ['Dependent']),
            ('buildbot.schedulers.forcesched', ['ForceScheduler']),
            ('buildbot.schedulers.timed', [
                'Periodic', 'Nightly', 'NightlyTriggerable']),
            ('buildbot.schedulers.trysched', [
                'Try_Jobdir', 'Try_Userpass'])
        ])
    ])
}

# set zip_safe to false to force Windows installs to always unpack eggs
# into directories, which seems to work better --
# see http://buildbot.net/trac/ticket/907
if sys.platform == "win32":
    setup_args['zip_safe'] = False

py_26 = sys.version_info[0] > 2 or (sys.version_info[0] == 2 and sys.version_info[1] >= 6)
if not py_26:
    raise RuntimeError("Buildbot master requires at least Python-2.6")

try:
    # If setuptools is installed, then we'll add setuptools-specific arguments
    # to the setup args.
    import setuptools  # @UnusedImport
except ImportError:
    pass
else:
    # dependencies
    if sys.version_info[0] == 2 and sys.version_info[1] <= 5:
        zi = 'zope.interface >= 3.6.1'  # the newest that works on Python 2.5
    else:
        zi = 'zope.interface >= 4.1.1'  # required for tests, but Twisted requires this anyway

    setup_args['install_requires'] = [
        'twisted >= 11.0.0',
        'Jinja2 >= 2.1',
        zi,
    ]

    setup_args['install_requires'] += [
        # sqlalchemy-0.8 betas show issues with sqlalchemy-0.7.2, so stick to 0.7.10
        'sqlalchemy >= 0.6, <= 0.7.10',
        # buildbot depends on sqlalchemy internals, and these are the tested
        # versions.
        'sqlalchemy-migrate ==0.7.0, ==0.7.1, ==0.7.2',
        'python-dateutil==1.5',
    ]
    setup_args['tests_require'] = [
        'mock',
    ]
    if os.getenv('NO_INSTALL_REQS'):
        setup_args['install_requires'] = None
        setup_args['tests_require'] = None

setup(**setup_args)

# Local Variables:
# fill-column: 71
# End:
