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
from setuptools import setup  # isort:skip


import glob
import inspect
import os
import pkg_resources
import sys
from distutils.command.install_data import install_data
from distutils.command.sdist import sdist
from pkg_resources import parse_version

from buildbot import version

BUILDING_WHEEL = bool("bdist_wheel" in sys.argv)


def include(d, e):
    """Generate a pair of (directory, file-list) for installation.

    'd' -- A directory
    'e' -- A glob pattern"""

    return (d, [f for f in glob.glob('{}/{}'.format(d, e)) if os.path.isfile(f)])


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
        super().finalize_options()

    def run(self):
        super().run()
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
        with open(src_fn) as f:
            src = f.read()
        src = src.replace('|version|', version)
        dst_fn = os.path.join(base_dir, 'NEWS')
        with open(dst_fn, 'w') as f:
            f.write(src)


def define_plugin_entry(name, module_name):
    """
    helper to produce lines suitable for setup.py's entry_points
    """
    if isinstance(name, tuple):
        entry, name = name
    else:
        entry = name
    return '{} = {}:{}'.format(entry, module_name, name)


def concat_dicts(*dicts):
    result = dict()
    for d in dicts:
        result.update(d)
    return result


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


__file__ = inspect.getframeinfo(inspect.currentframe()).filename

with open(os.path.join(os.path.dirname(__file__), 'README.rst')) as long_d_f:
    long_description = long_d_f.read()

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
    'classifiers': [
        'Development Status :: 5 - Production/Stable',
        'Environment :: No Input/Output (Daemon)',
        'Environment :: Web Environment',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: GNU General Public License v2 (GPLv2)',
        'Topic :: Software Development :: Build Tools',
        'Topic :: Software Development :: Testing',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
    ],

    'packages': [
        "buildbot",
        "buildbot.configurators",
        "buildbot.worker",
        "buildbot.worker.protocols",
        "buildbot.changes",
        "buildbot.clients",
        "buildbot.data",
        "buildbot.db",
        "buildbot.db.migrate.versions",
        "buildbot.db.types",
        "buildbot.machine",
        "buildbot.monkeypatches",
        "buildbot.mq",
        "buildbot.plugins",
        "buildbot.process",
        "buildbot.process.users",
        "buildbot.reporters",
        "buildbot.reporters.generators",
        "buildbot.schedulers",
        "buildbot.scripts",
        "buildbot.secrets",
        "buildbot.secrets.providers",
        "buildbot.statistics",
        "buildbot.statistics.storage_backends",
        "buildbot.steps",
        "buildbot.steps.package",
        "buildbot.steps.package.deb",
        "buildbot.steps.package.rpm",
        "buildbot.steps.source",
        "buildbot.util",
        "buildbot.wamp",
        "buildbot.www",
        "buildbot.www.hooks",
        "buildbot.www.authz",
    ] + ([] if BUILDING_WHEEL else [  # skip tests for wheels (save 50% of the archive)
        "buildbot.test",
        "buildbot.test.util",
        "buildbot.test.fake",
        "buildbot.test.fakedb",
        "buildbot.test.fuzz",
        "buildbot.test.integration",
        "buildbot.test.integration.interop",
        "buildbot.test.regressions",
        "buildbot.test.unit",
    ]),
    'data_files': [
        include("buildbot/reporters/templates", "*.txt"),
        ("buildbot/db/migrate", [
            "buildbot/db/migrate/migrate.cfg",
        ]),
        include("buildbot/db/migrate/versions", "*.py"),
        ("buildbot/scripts", [
            "buildbot/scripts/sample.cfg",
            "buildbot/scripts/buildbot_tac.tmpl",
        ]),
        include("buildbot/spec", "*.raml"),
        include("buildbot/spec/types", "*.raml"),
        include("buildbot/test/unit/test_templates_dir", "*.html"),
        include("buildbot/test/unit/test_templates_dir/plugin", "*.*"),
        include("buildbot/test/integration/pki", "*.*"),
        include("buildbot/test/integration/pki/ca", "*.*"),
    ] + include_statics("buildbot/www/static"),
    'cmdclass': {'install_data': install_data_twisted,
                 'sdist': our_sdist},
    'entry_points': concat_dicts(define_plugin_entries([
        ('buildbot.changes', [
            ('buildbot.changes.mail', [
                'MaildirSource', 'CVSMaildirSource',
                'SVNCommitEmailMaildirSource',
                'BzrLaunchpadEmailMaildirSource']),
            ('buildbot.changes.bitbucket', ['BitbucketPullrequestPoller']),
            ('buildbot.changes.github', ['GitHubPullrequestPoller']),
            ('buildbot.changes.gerritchangesource', [
                'GerritChangeSource', 'GerritEventLogPoller']),
            ('buildbot.changes.gitpoller', ['GitPoller']),
            ('buildbot.changes.hgpoller', ['HgPoller']),
            ('buildbot.changes.p4poller', ['P4Source']),
            ('buildbot.changes.pb', ['PBChangeSource']),
            ('buildbot.changes.svnpoller', ['SVNPoller'])
        ]),
        ('buildbot.schedulers', [
            ('buildbot.schedulers.basic', [
                'SingleBranchScheduler', 'AnyBranchScheduler']),
            ('buildbot.schedulers.dependent', ['Dependent']),
            ('buildbot.schedulers.triggerable', ['Triggerable']),
            ('buildbot.schedulers.forcesched', ['ForceScheduler']),
            ('buildbot.schedulers.timed', [
                'Periodic', 'Nightly', 'NightlyTriggerable']),
            ('buildbot.schedulers.trysched', [
                'Try_Jobdir', 'Try_Userpass'])
        ]),
        ('buildbot.secrets', [
            ('buildbot.secrets.providers.file', ['SecretInAFile']),
            ('buildbot.secrets.providers.passwordstore', ['SecretInPass']),
            ('buildbot.secrets.providers.vault', ['HashiCorpVaultSecretProvider'])
        ]),
        ('buildbot.worker', [
            ('buildbot.worker.base', ['Worker']),
            ('buildbot.worker.ec2', ['EC2LatentWorker']),
            ('buildbot.worker.libvirt', ['LibVirtWorker']),
            ('buildbot.worker.openstack', ['OpenStackLatentWorker']),
            ('buildbot.worker.docker', ['DockerLatentWorker']),
            ('buildbot.worker.kubernetes', ['KubeLatentWorker']),
            ('buildbot.worker.local', ['LocalWorker']),
        ]),
        ('buildbot.machine', [
            ('buildbot.machine.base', ['Machine']),
        ]),
        ('buildbot.steps', [
            ('buildbot.process.buildstep', ['BuildStep']),
            ('buildbot.steps.cmake', ['CMake']),
            ('buildbot.steps.cppcheck', ['Cppcheck']),
            ('buildbot.steps.gitdiffinfo', ['GitDiffInfo']),
            ('buildbot.steps.http', [
                'HTTPStep', 'POST', 'GET', 'PUT', 'DELETE', 'HEAD',
                'OPTIONS',
                'HTTPStepNewStyle', 'POSTNewStyle', 'GETNewStyle', 'PUTNewStyle', 'DELETENewStyle',
                'HEADNewStyle', 'OPTIONSNewStyle']),
            ('buildbot.steps.master', [
                'MasterShellCommand', 'MasterShellCommandNewStyle',
                'SetProperty', 'SetProperties', 'LogRenderable', "Assert"]),
            ('buildbot.steps.maxq', ['MaxQ']),
            ('buildbot.steps.mswin', ['Robocopy']),
            ('buildbot.steps.package.deb.lintian', ['DebLintian']),
            ('buildbot.steps.package.deb.pbuilder', [
                'DebPbuilder', 'DebCowbuilder', 'UbuPbuilder',
                'UbuCowbuilder']),
            ('buildbot.steps.package.rpm.mock', [
                'Mock', 'MockBuildSRPM', 'MockRebuild']),
            ('buildbot.steps.package.rpm.rpmbuild', ['RpmBuild']),
            ('buildbot.steps.package.rpm.rpmlint', ['RpmLint']),
            ('buildbot.steps.python', [
                'BuildEPYDoc', 'PyFlakes', 'PyLint', 'Sphinx']),
            ('buildbot.steps.python_twisted', [
                'HLint', 'Trial', 'RemovePYCs']),
            ('buildbot.steps.shell', [
                'ShellCommand', 'ShellCommandNewStyle', 'TreeSize',
                'SetPropertyFromCommand', 'SetPropertyFromCommandNewStyle',
                'Configure', 'ConfigureNewStyle',
                'WarningCountingShellCommand', 'WarningCountingShellCommandNewStyle',
                'Compile', 'CompileNewStyle',
                'Test', 'TestNewStyle', 'PerlModuleTest']),
            ('buildbot.steps.shellsequence', ['ShellSequence']),
            ('buildbot.steps.source.bzr', ['Bzr']),
            ('buildbot.steps.source.cvs', ['CVS']),
            ('buildbot.steps.source.darcs', ['Darcs']),
            ('buildbot.steps.source.gerrit', ['Gerrit']),
            ('buildbot.steps.source.git', ['Git', 'GitCommit', 'GitPush', 'GitTag']),
            ('buildbot.steps.source.github', ['GitHub']),
            ('buildbot.steps.source.gitlab', ['GitLab']),
            ('buildbot.steps.source.mercurial', ['Mercurial']),
            ('buildbot.steps.source.mtn', ['Monotone']),
            ('buildbot.steps.source.p4', ['P4']),
            ('buildbot.steps.source.repo', ['Repo']),
            ('buildbot.steps.source.svn', ['SVN']),
            ('buildbot.steps.subunit', ['SubunitShellCommand']),
            ('buildbot.steps.transfer', [
                'FileUpload', 'DirectoryUpload', 'MultipleFileUpload',
                'FileDownload', 'StringDownload', 'JSONStringDownload',
                'JSONPropertiesDownload']),
            ('buildbot.steps.trigger', ['Trigger']),
            ('buildbot.steps.vstudio', [
                'VC6', 'VC7', 'VS2003', 'VC8', 'VS2005', 'VCExpress9', 'VC9',
                'VS2008', 'VC10', 'VS2010', 'VC11', 'VS2012', 'VC12', 'VS2013',
                'VC14', 'VS2015', 'VC141', 'VS2017', 'MsBuild4', 'MsBuild',
                'MsBuild12', 'MsBuild14', 'MsBuild141']),
            ('buildbot.steps.worker', [
                'SetPropertiesFromEnv', 'FileExists', 'CopyDirectory',
                'RemoveDirectory', 'MakeDirectory']),
        ]),
        ('buildbot.reporters', [
            ('buildbot.reporters.generators.build', [
                'BuildStatusGenerator',
                'BuildStartEndStatusGenerator'
            ]),
            ('buildbot.reporters.generators.buildrequest', [
                'BuildRequestGenerator'
            ]),
            ('buildbot.reporters.generators.buildset', ['BuildSetStatusGenerator']),
            ('buildbot.reporters.generators.worker', ['WorkerMissingGenerator']),
            ('buildbot.reporters.mail', ['MailNotifier']),
            ('buildbot.reporters.pushjet', ['PushjetNotifier']),
            ('buildbot.reporters.pushover', ['PushoverNotifier']),
            ('buildbot.reporters.message', [
                'MessageFormatter',
                'MessageFormatterEmpty',
                'MessageFormatterFunction',
                'MessageFormatterMissingWorker',
                'MessageFormatterRenderable',
            ]),
            ('buildbot.reporters.gerrit', ['GerritStatusPush']),
            ('buildbot.reporters.gerrit_verify_status',
             ['GerritVerifyStatusPush']),
            ('buildbot.reporters.http', ['HttpStatusPush']),
            ('buildbot.reporters.github', ['GitHubStatusPush', 'GitHubCommentPush']),
            ('buildbot.reporters.gitlab', ['GitLabStatusPush']),
            ('buildbot.reporters.bitbucketserver', [
                'BitbucketServerStatusPush',
                'BitbucketServerCoreAPIStatusPush',
                'BitbucketServerPRCommentPush'
            ]),
            ('buildbot.reporters.bitbucket', ['BitbucketStatusPush']),
            ('buildbot.reporters.irc', ['IRC']),
            ('buildbot.reporters.telegram', ['TelegramBot']),
            ('buildbot.reporters.zulip', ['ZulipStatusPush']),
        ]),
        ('buildbot.util', [
            # Connection seems to be a way too generic name, though
            ('buildbot.worker.libvirt', ['Connection']),
            ('buildbot.changes.filter', ['ChangeFilter']),
            ('buildbot.changes.gerritchangesource', ['GerritChangeFilter']),
            ('buildbot.changes.svnpoller', [
                ('svn.split_file_projects_branches',
                 'split_file_projects_branches'),
                ('svn.split_file_branches', 'split_file_branches'),
                ('svn.split_file_alwaystrunk', 'split_file_alwaystrunk')]),
            ('buildbot.configurators.janitor', ['JanitorConfigurator']),
            ('buildbot.config', ['BuilderConfig']),
            ('buildbot.locks', [
                'MasterLock',
                'WorkerLock',
            ]),
            ('buildbot.manhole', [
                'AuthorizedKeysManhole', 'PasswordManhole', 'TelnetManhole']),
            ('buildbot.process.builder', [
                'enforceChosenWorker',
            ]),
            ('buildbot.process.factory', [
                'BuildFactory', 'GNUAutoconf', 'CPAN', 'Distutils', 'Trial',
                'BasicBuildFactory', 'QuickBuildFactory', 'BasicSVN']),
            ('buildbot.process.logobserver', ['LogLineObserver']),
            ('buildbot.process.properties', [
                'FlattenList', 'Interpolate', 'Property', 'Transform',
                'WithProperties', 'renderer', 'Secret']),
            ('buildbot.process.users.manual', [
                'CommandlineUserManager']),
            ('buildbot.revlinks', ['RevlinkMatch']),
            ('buildbot.reporters.utils', ['URLForBuild']),
            ('buildbot.schedulers.forcesched', [
                'AnyPropertyParameter', 'BooleanParameter',
                'ChoiceStringParameter',
                'CodebaseParameter', 'FileParameter', 'FixedParameter', 'InheritBuildParameter',
                'IntParameter', 'NestedParameter', 'ParameterGroup',
                'PatchParameter',
                'StringParameter', 'TextParameter', 'UserNameParameter',
                'WorkerChoiceParameter',
            ]),
            ('buildbot.process.results', [
                'Results', 'SUCCESS', 'WARNINGS', 'FAILURE', 'SKIPPED',
                'EXCEPTION', 'RETRY', 'CANCELLED']),
            ('buildbot.steps.source.repo', [
                ('repo.DownloadsFromChangeSource',
                 'RepoDownloadsFromChangeSource'),
                ('repo.DownloadsFromProperties',
                 'RepoDownloadsFromProperties')]),
            ('buildbot.steps.shellsequence', ['ShellArg']),
            ('buildbot.util.kubeclientservice', [
                'KubeHardcodedConfig', 'KubeCtlProxyConfigLoader', 'KubeInClusterConfigLoader'
            ]),
            ('buildbot.www.avatar', ['AvatarGravatar', 'AvatarGitHub']),
            ('buildbot.www.auth', [
                'UserPasswordAuth', 'HTPasswdAuth', 'RemoteUserAuth', 'CustomAuth']),
            ('buildbot.www.ldapuserinfo', ['LdapUserInfo']),
            ('buildbot.www.oauth2', [
                'GoogleAuth', 'GitHubAuth', 'GitLabAuth', 'BitbucketAuth']),
            ('buildbot.db.dbconfig', [
                'DbConfig']),
            ('buildbot.www.authz', [
                'Authz', 'fnmatchStrMatcher', 'reStrMatcher']),
            ('buildbot.www.authz.roles', [
                'RolesFromEmails', 'RolesFromGroups', 'RolesFromOwner', 'RolesFromUsername',
                'RolesFromDomain']),
            ('buildbot.www.authz.endpointmatchers', [
                'AnyEndpointMatcher', 'StopBuildEndpointMatcher', 'ForceBuildEndpointMatcher',
                'RebuildBuildEndpointMatcher', 'AnyControlEndpointMatcher',
                'EnableSchedulerEndpointMatcher'
            ]),
        ]),
        ('buildbot.webhooks', [
            ('buildbot.www.hooks.base', ['base']),
            ('buildbot.www.hooks.bitbucket', ['bitbucket']),
            ('buildbot.www.hooks.github', ['github']),
            ('buildbot.www.hooks.gitlab', ['gitlab']),
            ('buildbot.www.hooks.gitorious', ['gitorious']),
            ('buildbot.www.hooks.poller', ['poller']),
            ('buildbot.www.hooks.bitbucketcloud', ['bitbucketcloud']),
            ('buildbot.www.hooks.bitbucketserver', ['bitbucketserver'])
        ])
    ]), {
        'console_scripts': [
            'buildbot=buildbot.scripts.runner:run',
            # this will also be shipped on non windows :-(
            'buildbot_windows_service=buildbot.scripts.windows_service:HandleCommandLine',
        ]}
    )
}

# set zip_safe to false to force Windows installs to always unpack eggs
# into directories, which seems to work better --
# see http://buildbot.net/trac/ticket/907
if sys.platform == "win32":
    setup_args['zip_safe'] = False

py_36 = sys.version_info[0] > 3 or (
    sys.version_info[0] == 3 and sys.version_info[1] >= 6)
if not py_36:
    raise RuntimeError("Buildbot master requires at least Python-3.6")

# pip<1.4 doesn't have the --pre flag, and will thus attempt to install alpha
# and beta versions of Buildbot.  Prevent that from happening.
VERSION_MSG = """
This is a pre-release version of Buildbot, which can only be installed with
pip-1.4 or later Try installing the latest stable version of Buildbot instead:
    pip install buildbot==0.8.12
See https://pypi.python.org/pypi/buildbot to verify the current stable version.
"""
if 'a' in version or 'b' in version:
    try:
        pip_dist = pkg_resources.get_distribution('pip')
    except pkg_resources.DistributionNotFound:
        pip_dist = None

    if pip_dist:
        if parse_version(pip_dist.version) < parse_version('1.4'):
            raise RuntimeError(VERSION_MSG)

twisted_ver = ">= 17.9.0"
autobahn_ver = ">= 0.16.0"
txaio_ver = ">= 2.2.2"

bundle_version = version.split("-")[0]

# dependencies
setup_args['install_requires'] = [
    'setuptools >= 8.0',
    'Twisted ' + twisted_ver,
    'Jinja2 >= 2.1',
    # required for tests, but Twisted requires this anyway
    'zope.interface >= 4.1.1',
    'sqlalchemy >= 1.2.0, < 1.4',
    'sqlalchemy-migrate>=0.13',
    'python-dateutil>=1.5',
    'txaio ' + txaio_ver,
    'autobahn ' + autobahn_ver,
    'PyJWT',
    'pyyaml'
]

# Unit test dependencies.
test_deps = [
    # http client libraries
    'treq',
    'txrequests',
    # pypugjs required for custom templates tests
    'pypugjs',
    # boto3 and moto required for running EC2 tests
    'boto3',
    'moto',
    'mock>=2.0.0',
    'parameterized',
]
if sys.platform != 'win32':
    test_deps += [
        # LZ4 fails to build on Windows:
        # https://github.com/steeve/python-lz4/issues/27
        # lz4 required for log compression tests.
        'lz4',
    ]

setup_args['tests_require'] = test_deps

setup_args['extras_require'] = {
    'test': [
        'setuptools_trial',
        'isort',
        # spellcheck introduced in version 1.4.0
        'pylint<1.7.0',
        'pyenchant',
        'flake8~=2.6.0',
    ] + test_deps,
    'bundle': [
        "buildbot-www=={0}".format(bundle_version),
        "buildbot-worker=={0}".format(bundle_version),
        "buildbot-waterfall-view=={0}".format(bundle_version),
        "buildbot-console-view=={0}".format(bundle_version),
        "buildbot-grid-view=={0}".format(bundle_version),
    ],
    'tls': [
        'Twisted[tls] ' + twisted_ver,
        # There are bugs with extras inside extras:
        # <https://github.com/pypa/pip/issues/3516>
        # so we explicitly include Twisted[tls] dependencies.
        'pyopenssl >= 16.0.0',
        'service_identity',
        'idna >= 0.6',
    ],
    'docs': [
        'docutils>=0.16.0',
        'sphinx>=3.2.0',
        'sphinx-rtd-theme>=0.5',
        'sphinxcontrib-blockdiag',
        'sphinxcontrib-spelling',
        'sphinxcontrib-websupport',
        'pyenchant',
        'sphinx-jinja',
        'towncrier',
    ],
}

if '--help-commands' in sys.argv or 'trial' in sys.argv or 'test' in sys.argv:
    setup_args['setup_requires'] = [
        'setuptools_trial',
    ]

if os.getenv('NO_INSTALL_REQS'):
    setup_args['install_requires'] = None
    setup_args['extras_require'] = None

if __name__ == '__main__':
    setup(**setup_args)

# Local Variables:
# fill-column: 71
# End:
