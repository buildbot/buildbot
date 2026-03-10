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

from __future__ import annotations

import os

from setuptools import setup
from setuptools.command.egg_info import egg_info
from setuptools.command.sdist import sdist


class our_egg_info(egg_info):
    def run(self) -> None:
        version = self.distribution.get_version()

        # Pin bundle version

        # has to recreate the dict as it's immutable
        metadata = self.distribution.metadata
        metadata.extras_require = dict(metadata.extras_require)

        bundle_version = version.split("-", 1)[0]
        metadata.extras_require['bundle'] = [
            f"{package}=={bundle_version}" for package in metadata.extras_require['bundle']
        ]
        super().run()


class our_sdist(sdist):
    def make_release_tree(self, base_dir: str, files: list[str]) -> None:
        sdist.make_release_tree(self, base_dir, files)
        # ensure that NEWS has a copy of the latest release notes, with the
        # proper version substituted
        src_fn = os.path.join('docs', 'relnotes/index.rst')
        with open(src_fn) as f:
            src = f.read()
        version = self.distribution.get_version()
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
    return f'{entry} = {module_name}:{name}'


def concat_dicts(*dicts):
    result = {}
    for d in dicts:
        result.update(d)
    return result


def define_plugin_entries(groups):
    """
    helper to all groups for plugins
    """
    result = {}

    for group, modules in groups:
        tempo = []
        for module_name, names in modules:
            tempo.extend([define_plugin_entry(name, module_name) for name in names])
        result[group] = tempo

    return result


setup_args = {
    'cmdclass': {'egg_info': our_egg_info, 'sdist': our_sdist},
    'entry_points': concat_dicts(
        define_plugin_entries([
            (
                'buildbot.changes',
                [
                    (
                        'buildbot.changes.mail',
                        [
                            'MaildirSource',
                            'CVSMaildirSource',
                            'SVNCommitEmailMaildirSource',
                            'BzrLaunchpadEmailMaildirSource',
                        ],
                    ),
                    ('buildbot.changes.bitbucket', ['BitbucketPullrequestPoller']),
                    ('buildbot.changes.github', ['GitHubPullrequestPoller']),
                    (
                        'buildbot.changes.gerritchangesource',
                        ['GerritChangeSource', 'GerritEventLogPoller'],
                    ),
                    ('buildbot.changes.gitpoller', ['GitPoller']),
                    ('buildbot.changes.hgpoller', ['HgPoller']),
                    ('buildbot.changes.p4poller', ['P4Source']),
                    ('buildbot.changes.pb', ['PBChangeSource']),
                    ('buildbot.changes.svnpoller', ['SVNPoller']),
                ],
            ),
            (
                'buildbot.schedulers',
                [
                    ('buildbot.schedulers.basic', ['SingleBranchScheduler', 'AnyBranchScheduler']),
                    ('buildbot.schedulers.dependent', ['Dependent']),
                    ('buildbot.schedulers.triggerable', ['Triggerable']),
                    ('buildbot.schedulers.forcesched', ['ForceScheduler']),
                    ('buildbot.schedulers.timed', ['Periodic', 'Nightly', 'NightlyTriggerable']),
                    ('buildbot.schedulers.trysched', ['Try_Jobdir', 'Try_Userpass']),
                ],
            ),
            (
                'buildbot.secrets',
                [
                    ('buildbot.secrets.providers.file', ['SecretInAFile']),
                    ('buildbot.secrets.providers.passwordstore', ['SecretInPass']),
                    (
                        'buildbot.secrets.providers.vault_hvac',
                        [
                            'HashiCorpVaultKvSecretProvider',
                            'VaultAuthenticatorToken',
                            'VaultAuthenticatorApprole',
                        ],
                    ),
                ],
            ),
            (
                'buildbot.worker',
                [
                    ('buildbot.worker.base', ['Worker']),
                    ('buildbot.worker.ec2', ['EC2LatentWorker']),
                    ('buildbot.worker.libvirt', ['LibVirtWorker']),
                    ('buildbot.worker.openstack', ['OpenStackLatentWorker']),
                    ('buildbot.worker.docker', ['DockerLatentWorker']),
                    ('buildbot.worker.kubernetes', ['KubeLatentWorker']),
                    ('buildbot.worker.local', ['LocalWorker']),
                ],
            ),
            (
                'buildbot.machine',
                [
                    ('buildbot.machine.base', ['Machine']),
                ],
            ),
            (
                'buildbot.steps',
                [
                    ('buildbot.process.buildstep', ['BuildStep']),
                    ('buildbot.steps.cmake', ['CMake']),
                    (
                        'buildbot.steps.configurable',
                        ['BuildbotTestCiTrigger', 'BuildbotCiSetupSteps'],
                    ),
                    ('buildbot.steps.cppcheck', ['Cppcheck']),
                    ('buildbot.steps.gitdiffinfo', ['GitDiffInfo']),
                    (
                        'buildbot.steps.http',
                        ['HTTPStep', 'POST', 'GET', 'PUT', 'DELETE', 'HEAD', 'OPTIONS'],
                    ),
                    (
                        'buildbot.steps.master',
                        [
                            'MasterShellCommand',
                            'SetProperty',
                            'SetProperties',
                            'LogRenderable',
                            "Assert",
                        ],
                    ),
                    ('buildbot.steps.maxq', ['MaxQ']),
                    ('buildbot.steps.mswin', ['Robocopy']),
                    ('buildbot.steps.package.deb.lintian', ['DebLintian']),
                    (
                        'buildbot.steps.package.deb.pbuilder',
                        ['DebPbuilder', 'DebCowbuilder', 'UbuPbuilder', 'UbuCowbuilder'],
                    ),
                    ('buildbot.steps.package.rpm.mock', ['Mock', 'MockBuildSRPM', 'MockRebuild']),
                    ('buildbot.steps.package.rpm.rpmbuild', ['RpmBuild']),
                    ('buildbot.steps.package.rpm.rpmlint', ['RpmLint']),
                    ('buildbot.steps.python', ['BuildEPYDoc', 'PyFlakes', 'PyLint', 'Sphinx']),
                    ('buildbot.steps.python_twisted', ['HLint', 'Trial', 'RemovePYCs']),
                    (
                        'buildbot.steps.shell',
                        [
                            'ShellCommand',
                            'TreeSize',
                            'SetPropertyFromCommand',
                            'Configure',
                            'WarningCountingShellCommand',
                            'Compile',
                            'Test',
                            'PerlModuleTest',
                        ],
                    ),
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
                    (
                        'buildbot.steps.transfer',
                        [
                            'FileUpload',
                            'DirectoryUpload',
                            'MultipleFileUpload',
                            'FileDownload',
                            'StringDownload',
                            'JSONStringDownload',
                            'JSONPropertiesDownload',
                        ],
                    ),
                    ('buildbot.steps.trigger', ['Trigger']),
                    (
                        'buildbot.steps.vstudio',
                        [
                            'VC6',
                            'VC7',
                            'VS2003',
                            'VC8',
                            'VS2005',
                            'VCExpress9',
                            'VC9',
                            'VS2008',
                            'VC10',
                            'VS2010',
                            'VC11',
                            'VS2012',
                            'VC12',
                            'VS2013',
                            'VC14',
                            'VS2015',
                            'VC141',
                            'VS2017',
                            'VS2019',
                            'VS2022',
                            'MsBuild4',
                            'MsBuild',
                            'MsBuild12',
                            'MsBuild14',
                            'MsBuild141',
                            'MsBuild15',
                            'MsBuild16',
                            'MsBuild17',
                        ],
                    ),
                    (
                        'buildbot.steps.worker',
                        [
                            'SetPropertiesFromEnv',
                            'FileExists',
                            'CopyDirectory',
                            'RemoveDirectory',
                            'MakeDirectory',
                        ],
                    ),
                ],
            ),
            (
                'buildbot.reporters',
                [
                    (
                        'buildbot.reporters.generators.build',
                        ['BuildStatusGenerator', 'BuildStartEndStatusGenerator'],
                    ),
                    ('buildbot.reporters.generators.buildrequest', ['BuildRequestGenerator']),
                    (
                        "buildbot.reporters.generators.buildset",
                        [
                            "BuildSetCombinedStatusGenerator",
                            "BuildSetStatusGenerator",
                        ],
                    ),
                    ('buildbot.reporters.generators.worker', ['WorkerMissingGenerator']),
                    ('buildbot.reporters.mail', ['MailNotifier']),
                    ('buildbot.reporters.pushjet', ['PushjetNotifier']),
                    ('buildbot.reporters.pushover', ['PushoverNotifier']),
                    (
                        'buildbot.reporters.message',
                        [
                            'MessageFormatter',
                            'MessageFormatterEmpty',
                            'MessageFormatterFunction',
                            "MessageFormatterFunctionRaw",
                            'MessageFormatterMissingWorker',
                            'MessageFormatterRenderable',
                        ],
                    ),
                    ('buildbot.reporters.gerrit', ['GerritStatusPush']),
                    ('buildbot.reporters.gerrit_verify_status', ['GerritVerifyStatusPush']),
                    ('buildbot.reporters.http', ['HttpStatusPush']),
                    ('buildbot.reporters.github', ['GitHubStatusPush', 'GitHubCommentPush']),
                    ('buildbot.reporters.gitlab', ['GitLabStatusPush']),
                    (
                        'buildbot.reporters.bitbucketserver',
                        [
                            'BitbucketServerStatusPush',
                            'BitbucketServerCoreAPIStatusPush',
                            'BitbucketServerPRCommentPush',
                        ],
                    ),
                    ('buildbot.reporters.bitbucket', ['BitbucketStatusPush']),
                    ('buildbot.reporters.irc', ['IRC']),
                    ('buildbot.reporters.telegram', ['TelegramBot']),
                    ('buildbot.reporters.zulip', ['ZulipStatusPush']),
                ],
            ),
            (
                'buildbot.util',
                [
                    # Connection seems to be a way too generic name, though
                    ('buildbot.worker.libvirt', ['Connection']),
                    ('buildbot.changes.filter', ['ChangeFilter']),
                    ('buildbot.changes.gerritchangesource', ['GerritChangeFilter']),
                    (
                        'buildbot.changes.svnpoller',
                        [
                            ('svn.split_file_projects_branches', 'split_file_projects_branches'),
                            ('svn.split_file_branches', 'split_file_branches'),
                            ('svn.split_file_alwaystrunk', 'split_file_alwaystrunk'),
                        ],
                    ),
                    ('buildbot.configurators.janitor', ['JanitorConfigurator']),
                    ('buildbot.config.builder', ['BuilderConfig']),
                    (
                        'buildbot.locks',
                        [
                            'MasterLock',
                            'WorkerLock',
                        ],
                    ),
                    (
                        'buildbot.manhole',
                        ['AuthorizedKeysManhole', 'PasswordManhole', 'TelnetManhole'],
                    ),
                    (
                        'buildbot.process.builder',
                        [
                            'enforceChosenWorker',
                        ],
                    ),
                    (
                        'buildbot.process.codebase',
                        [
                            'Codebase',
                        ],
                    ),
                    (
                        'buildbot.process.factory',
                        [
                            'BuildFactory',
                            'GNUAutoconf',
                            'CPAN',
                            'Distutils',
                            'Trial',
                            'BasicBuildFactory',
                            'QuickBuildFactory',
                            'BasicSVN',
                        ],
                    ),
                    ('buildbot.process.logobserver', ['LogLineObserver']),
                    ('buildbot.process.project', ['Project']),
                    (
                        'buildbot.process.properties',
                        [
                            'FlattenList',
                            'Interpolate',
                            'Property',
                            'Transform',
                            'WithProperties',
                            'renderer',
                            'Secret',
                        ],
                    ),
                    ('buildbot.process.users.manual', ['CommandlineUserManager']),
                    ('buildbot.revlinks', ['RevlinkMatch']),
                    ('buildbot.reporters.utils', ['URLForBuild']),
                    ('buildbot.schedulers.canceller', ['OldBuildCanceller']),
                    ('buildbot.schedulers.canceller_buildset', ['FailingBuildsetCanceller']),
                    (
                        'buildbot.schedulers.forcesched',
                        [
                            'AnyPropertyParameter',
                            'BooleanParameter',
                            'ChoiceStringParameter',
                            'CodebaseParameter',
                            'FileParameter',
                            'FixedParameter',
                            'InheritBuildParameter',
                            'IntParameter',
                            'NestedParameter',
                            'ParameterGroup',
                            'PatchParameter',
                            'StringParameter',
                            'TextParameter',
                            'UserNameParameter',
                            'WorkerChoiceParameter',
                        ],
                    ),
                    (
                        'buildbot.process.results',
                        [
                            'Results',
                            'SUCCESS',
                            'WARNINGS',
                            'FAILURE',
                            'SKIPPED',
                            'EXCEPTION',
                            'RETRY',
                            'CANCELLED',
                        ],
                    ),
                    (
                        'buildbot.steps.source.repo',
                        [
                            ('repo.DownloadsFromChangeSource', 'RepoDownloadsFromChangeSource'),
                            ('repo.DownloadsFromProperties', 'RepoDownloadsFromProperties'),
                        ],
                    ),
                    ('buildbot.steps.shellsequence', ['ShellArg']),
                    (
                        'buildbot.util.git_credential',
                        ['GitCredentialInputRenderer', 'GitCredentialOptions'],
                    ),
                    (
                        'buildbot.util.kubeclientservice',
                        [
                            'KubeHardcodedConfig',
                            'KubeCtlProxyConfigLoader',
                            'KubeInClusterConfigLoader',
                        ],
                    ),
                    ('buildbot.util.ssfilter', ['SourceStampFilter']),
                    ('buildbot.www.avatar', ['AvatarGravatar', 'AvatarGitHub']),
                    (
                        'buildbot.www.auth',
                        ['UserPasswordAuth', 'HTPasswdAuth', 'RemoteUserAuth', 'CustomAuth'],
                    ),
                    ('buildbot.www.ldapuserinfo', ['LdapUserInfo']),
                    (
                        'buildbot.www.oauth2',
                        ['GoogleAuth', 'GitHubAuth', 'GitLabAuth', 'BitbucketAuth', 'KeyCloakAuth'],
                    ),
                    ('buildbot.db.dbconfig', ['DbConfig']),
                    ('buildbot.www.authz', ['Authz', 'fnmatchStrMatcher', 'reStrMatcher']),
                    (
                        'buildbot.www.authz.roles',
                        [
                            'RolesFromEmails',
                            'RolesFromGroups',
                            'RolesFromOwner',
                            'RolesFromUsername',
                            'RolesFromDomain',
                        ],
                    ),
                    (
                        'buildbot.www.authz.endpointmatchers',
                        [
                            'AnyEndpointMatcher',
                            'StopBuildEndpointMatcher',
                            'ForceBuildEndpointMatcher',
                            'RebuildBuildEndpointMatcher',
                            'AnyControlEndpointMatcher',
                            'EnableSchedulerEndpointMatcher',
                        ],
                    ),
                ],
            ),
            (
                'buildbot.webhooks',
                [
                    ('buildbot.www.hooks.base', ['base']),
                    ('buildbot.www.hooks.bitbucket', ['bitbucket']),
                    ('buildbot.www.hooks.github', ['github']),
                    ('buildbot.www.hooks.gitlab', ['gitlab']),
                    ('buildbot.www.hooks.gitorious', ['gitorious']),
                    ('buildbot.www.hooks.poller', ['poller']),
                    ('buildbot.www.hooks.bitbucketcloud', ['bitbucketcloud']),
                    ('buildbot.www.hooks.bitbucketserver', ['bitbucketserver']),
                ],
            ),
        ]),
        {
            'console_scripts': [
                'buildbot=buildbot.scripts.runner:run',
                # this will also be shipped on non windows :-(
                'buildbot_windows_service=buildbot.scripts.windows_service:HandleCommandLine',
            ]
        },
    ),
}

if __name__ == '__main__':
    setup(**setup_args)
