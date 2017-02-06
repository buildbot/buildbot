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

from __future__ import absolute_import
from __future__ import print_function
from future.builtins import range

from twisted.trial import unittest

from buildbot.changes.changes import Change
from buildbot.process.properties import Properties
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps.source import repo
from buildbot.test.fake.remotecommand import Expect
from buildbot.test.fake.remotecommand import ExpectShell
from buildbot.test.util import sourcesteps

from .test_changes_gerritchangesource import TestGerritChangeSource


class RepoURL(unittest.TestCase):
    # testcases taken from old_source/Repo test

    def oneTest(self, props, expected):
        p = Properties()
        p.update(props, "test")
        r = repo.RepoDownloadsFromProperties(list(props))
        self.assertEqual(sorted(r.getRenderingFor(p)), sorted(expected))

    def test_parse1(self):
        self.oneTest(
            {'a': "repo download test/bla 564/12"}, ["test/bla 564/12"])

    def test_parse2(self):
        self.oneTest(
            {'a':
                "repo download test/bla 564/12 repo download test/bla 564/2"},
            ["test/bla 564/12", "test/bla 564/2"])
        self.oneTest({'a': "repo download test/bla 564/12", 'b': "repo download test/bla 564/2"}, [
                     "test/bla 564/12", "test/bla 564/2"])

    def test_parse3(self):
        self.oneTest({'a': "repo download test/bla 564/12 repo download test/bla 564/2 test/foo 5/1"}, [
                     "test/bla 564/12", "test/bla 564/2", "test/foo 5/1"])
        self.oneTest(
            {'a': "repo download test/bla 564/12"}, ["test/bla 564/12"])


class TestRepo(sourcesteps.SourceStepMixin, unittest.TestCase):

    def setUp(self):
        self.shouldRetry = False
        self.logEnviron = True
        return self.setUpSourceStep()

    def tearDown(self):
        return self.tearDownSourceStep()

    def shouldLogEnviron(self):
        r = self.logEnviron
        self.logEnviron = False
        return r

    def ExpectShell(self, **kw):
        if 'workdir' not in kw:
            kw['workdir'] = 'wkdir'
        if 'logEnviron' not in kw:
            kw['logEnviron'] = self.shouldLogEnviron()
        return ExpectShell(**kw)

    def mySetupStep(self, **kwargs):
        if "repoDownloads" not in kwargs:
            kwargs.update(
                dict(repoDownloads=repo.RepoDownloadsFromProperties(["repo_download", "repo_download2"])))
        self.setupStep(
            repo.Repo(manifestURL='git://myrepo.com/manifest.git',
                      manifestBranch="mb",
                      manifestFile="mf",
                      **kwargs))
        self.build.allChanges = lambda x=None: []

    def myRunStep(self, result=SUCCESS, state_string=None):
        self.expectOutcome(result=result, state_string=state_string)
        return self.runStep()

    def expectClobber(self):
        # stat return 1 so we clobber
        self.expectCommands(
            Expect('stat', dict(file='wkdir/.repo',
                                logEnviron=self.logEnviron))
            + 1,
            Expect('rmdir', dict(dir='wkdir',
                                 logEnviron=self.logEnviron))
            + 0,
            Expect('mkdir', dict(dir='wkdir',
                                 logEnviron=self.logEnviron))
            + 0,
        )

    def expectnoClobber(self):
        # stat return 0, so nothing
        self.expectCommands(
            Expect('stat', dict(file='wkdir/.repo',
                                logEnviron=self.logEnviron))
            + 0,
        )

    def expectRepoSync(self, which_fail=-1, breakatfail=False, depth=0,
                       syncoptions=["-c"], override_commands=[]):
        commands = [
            self.ExpectShell(
                command=[
                    'bash', '-c', self.step._getCleanupCommand()]),
            self.ExpectShell(
                command=['repo', 'init', '-u', 'git://myrepo.com/manifest.git',
                         '-b', 'mb', '-m', 'mf', '--depth', str(depth)])
        ] + override_commands + [
            self.ExpectShell(command=['repo', 'sync'] + syncoptions),
            self.ExpectShell(
                command=['repo', 'manifest', '-r', '-o', 'manifest-original.xml'])
        ]
        for i in range(len(commands)):
            self.expectCommands(commands[i] + (which_fail == i and 1 or 0))
            if which_fail == i and breakatfail:
                break

    def test_basic(self):
        """basic first time repo sync"""
        self.mySetupStep(repoDownloads=None)
        self.expectClobber()
        self.expectRepoSync()
        return self.myRunStep()

    def test_basic_depth(self):
        """basic first time repo sync"""
        self.mySetupStep(repoDownloads=None, depth=2)
        self.expectClobber()
        self.expectRepoSync(depth=2)
        return self.myRunStep()

    def test_update(self):
        """basic second time repo sync"""
        self.mySetupStep()
        self.expectnoClobber()
        self.expectRepoSync()
        return self.myRunStep()

    def test_jobs(self):
        """basic first time repo sync with jobs"""
        self.mySetupStep(jobs=2)
        self.expectClobber()
        self.expectRepoSync(syncoptions=["-j2", "-c"])
        return self.myRunStep()

    def test_sync_all_branches(self):
        """basic first time repo sync with all branches"""
        self.mySetupStep(syncAllBranches=True)
        self.expectClobber()
        self.expectRepoSync(syncoptions=[])
        return self.myRunStep()

    def test_manifest_override(self):
        """repo sync with manifest_override_url property set
        download via wget
        """
        self.mySetupStep(manifestOverrideUrl="http://u.rl/test.manifest",
                         syncAllBranches=True)
        self.expectClobber()
        override_commands = [
            Expect(
                'stat', dict(file='wkdir/http://u.rl/test.manifest',
                             logEnviron=False)),
            self.ExpectShell(logEnviron=False, command=['wget',
                                                        'http://u.rl/test.manifest',
                                                        '-O', 'manifest_override.xml']),
            self.ExpectShell(
                logEnviron=False, workdir='wkdir/.repo',
                command=['ln', '-sf', '../manifest_override.xml',
                         'manifest.xml'])
        ]
        self.expectRepoSync(which_fail=2, syncoptions=[],
                            override_commands=override_commands)
        return self.myRunStep()

    def test_manifest_override_local(self):
        """repo sync with manifest_override_url property set
        copied from local FS
        """
        self.mySetupStep(manifestOverrideUrl="test.manifest",
                         syncAllBranches=True)
        self.expectClobber()
        override_commands = [
            Expect('stat', dict(file='wkdir/test.manifest',
                                logEnviron=False)),
            self.ExpectShell(logEnviron=False,
                             command=[
                                 'cp', '-f', 'test.manifest', 'manifest_override.xml']),
            self.ExpectShell(logEnviron=False,
                             workdir='wkdir/.repo',
                             command=['ln', '-sf', '../manifest_override.xml',
                                      'manifest.xml'])
        ]
        self.expectRepoSync(
            syncoptions=[], override_commands=override_commands)
        return self.myRunStep()

    def test_tarball(self):
        """repo sync using the tarball cache
        """
        self.mySetupStep(tarball="/tarball.tar")
        self.expectClobber()
        self.expectCommands(
            self.ExpectShell(command=['tar', '-xvf', '/tarball.tar']) + 0)
        self.expectRepoSync()
        self.expectCommands(self.ExpectShell(command=['stat', '-c%Y', '/tarball.tar'])
                            + Expect.log('stdio', stdout=str(10000))
                            + 0)
        self.expectCommands(self.ExpectShell(command=['stat', '-c%Y', '.'])
                            + Expect.log(
                                'stdio', stdout=str(10000 + 7 * 24 * 3600))
                            + 0)
        return self.myRunStep()

    def test_create_tarball(self):
        """repo sync create the tarball if its not here
        """
        self.mySetupStep(tarball="/tarball.tgz")
        self.expectClobber()
        self.expectCommands(
            self.ExpectShell(
                command=['tar', '-z', '-xvf', '/tarball.tgz']) + 1,
            self.ExpectShell(command=['rm', '-f', '/tarball.tgz']) + 1,
            Expect('rmdir', dict(dir='wkdir/.repo',
                                 logEnviron=False))
            + 1)
        self.expectRepoSync()
        self.expectCommands(self.ExpectShell(command=['stat', '-c%Y', '/tarball.tgz'])
                            + Expect.log('stdio', stderr="file not found!")
                            + 1,
                            self.ExpectShell(command=['tar', '-z',
                                                      '-cvf', '/tarball.tgz', '.repo'])
                            + 0)
        return self.myRunStep()

    def do_test_update_tarball(self, suffix, option):
        """repo sync update the tarball cache at the end (tarball older than a week)
        """
        self.mySetupStep(tarball="/tarball." + suffix)
        self.expectClobber()
        self.expectCommands(
            self.ExpectShell(command=['tar'] + option + ['-xvf', '/tarball.' + suffix]) + 0)
        self.expectRepoSync()
        self.expectCommands(self.ExpectShell(command=['stat', '-c%Y', '/tarball.' + suffix])
                            + Expect.log('stdio', stdout=str(10000))
                            + 0,
                            self.ExpectShell(command=['stat', '-c%Y', '.'])
                            + Expect.log(
                                'stdio', stdout=str(10001 + 7 * 24 * 3600))
                            + 0,
                            self.ExpectShell(command=['tar'] + option +
                                             ['-cvf', '/tarball.' + suffix, '.repo'])
                            + 0)
        return self.myRunStep()

    def test_update_tarball(self):
        self.do_test_update_tarball("tar", [])

    def test_update_tarball_gz(self):
        """tarball compression variants"""
        self.do_test_update_tarball("tar.gz", ["-z"])

    def test_update_tarball_tgz(self):
        self.do_test_update_tarball("tgz", ["-z"])

    def test_update_tarball_bzip(self):
        self.do_test_update_tarball("tar.bz2", ["-j"])

    def test_update_tarball_lzma(self):
        self.do_test_update_tarball("tar.lzma", ["--lzma"])

    def test_update_tarball_lzop(self):
        self.do_test_update_tarball("tar.lzop", ["--lzop"])

    def test_update_tarball_fail1(self, suffix="tar", option=[]):
        """tarball extract fail -> remove the tarball + remove .repo dir
        """
        self.mySetupStep(tarball="/tarball." + suffix)
        self.expectClobber()
        self.expectCommands(
            self.ExpectShell(
                command=[
                    'tar'] + option + ['-xvf', '/tarball.' + suffix]) + 1,
            self.ExpectShell(
                command=['rm', '-f', '/tarball.tar']) + 0,
            Expect(
                'rmdir', dict(dir='wkdir/.repo',
                              logEnviron=False))
            + 0)
        self.expectRepoSync()
        self.expectCommands(self.ExpectShell(command=['stat', '-c%Y', '/tarball.' + suffix])
                            + Expect.log('stdio', stdout=str(10000))
                            + 0,
                            self.ExpectShell(command=['stat', '-c%Y', '.'])
                            + Expect.log(
                                'stdio', stdout=str(10001 + 7 * 24 * 3600))
                            + 0,
                            self.ExpectShell(command=['tar'] + option +
                                             ['-cvf', '/tarball.' + suffix, '.repo'])
                            + 0)
        return self.myRunStep()

    def test_update_tarball_fail2(self, suffix="tar", option=[]):
        """tarball update fail -> remove the tarball + continue repo download
        """
        self.mySetupStep(tarball="/tarball." + suffix)
        self.build.setProperty("repo_download",
                               "repo download test/bla 564/12", "test")
        self.expectClobber()
        self.expectCommands(
            self.ExpectShell(command=['tar'] + option + ['-xvf', '/tarball.' + suffix]) + 0)
        self.expectRepoSync()
        self.expectCommands(self.ExpectShell(command=['stat', '-c%Y', '/tarball.' + suffix])
                            + Expect.log('stdio', stdout=str(10000))
                            + 0,
                            self.ExpectShell(command=['stat', '-c%Y', '.'])
                            + Expect.log(
                                'stdio', stdout=str(10001 + 7 * 24 * 3600))
                            + 0,
                            self.ExpectShell(command=['tar'] + option +
                                             ['-cvf', '/tarball.' + suffix, '.repo'])
                            + 1,
                            self.ExpectShell(
                                command=['rm', '-f', '/tarball.tar']) + 0,
                            self.ExpectShell(
                                command=['repo', 'download', 'test/bla', '564/12'])
                            + 0)
        return self.myRunStep()

    def test_repo_downloads(self):
        """basic repo download, and check that repo_downloaded is updated"""
        self.mySetupStep()
        self.build.setProperty("repo_download",
                               "repo download test/bla 564/12", "test")
        self.expectnoClobber()
        self.expectRepoSync()
        self.expectCommands(
            self.ExpectShell(
                command=['repo', 'download', 'test/bla', '564/12'])
            + 0
            + Expect.log(
                'stdio', stderr="test/bla refs/changes/64/564/12 -> FETCH_HEAD\n")
            + Expect.log('stdio', stderr="HEAD is now at 0123456789abcdef...\n"))
        self.expectProperty(
            "repo_downloaded", "564/12 0123456789abcdef ", "Source")
        return self.myRunStep()

    def test_repo_downloads2(self):
        """2 repo downloads"""
        self.mySetupStep()
        self.build.setProperty("repo_download",
                               "repo download test/bla 564/12", "test")
        self.build.setProperty("repo_download2",
                               "repo download test/bla2 565/12", "test")
        self.expectnoClobber()
        self.expectRepoSync()
        self.expectCommands(
            self.ExpectShell(
                command=['repo', 'download', 'test/bla', '564/12'])
            + 0,
            self.ExpectShell(
                command=['repo', 'download', 'test/bla2', '565/12'])
            + 0)
        return self.myRunStep()

    def test_repo_download_manifest(self):
        """2 repo downloads, with one manifest patch"""
        self.mySetupStep()
        self.build.setProperty("repo_download",
                               "repo download test/bla 564/12", "test")
        self.build.setProperty("repo_download2",
                               "repo download manifest 565/12", "test")
        self.expectnoClobber()
        self.expectCommands(
            self.ExpectShell(
                command=['bash', '-c', self.step._getCleanupCommand()])
            + 0,
            self.ExpectShell(
                command=['repo', 'init', '-u', 'git://myrepo.com/manifest.git',
                         '-b', 'mb', '-m', 'mf', '--depth', '0'])
            + 0,
            self.ExpectShell(
                workdir='wkdir/.repo/manifests',
                command=[
                    'git', 'fetch', 'git://myrepo.com/manifest.git',
                    'refs/changes/65/565/12'])
            + 0,
            self.ExpectShell(
                workdir='wkdir/.repo/manifests',
                command=['git', 'cherry-pick', 'FETCH_HEAD'])
            + 0,
            self.ExpectShell(command=['repo', 'sync', '-c'])
            + 0,
            self.ExpectShell(
                command=['repo', 'manifest', '-r', '-o', 'manifest-original.xml'])
            + 0)
        self.expectCommands(
            self.ExpectShell(
                command=['repo', 'download', 'test/bla', '564/12'])
            + 0)
        return self.myRunStep()

    def test_repo_downloads_mirror_sync(self):
        """repo downloads, with mirror synchronization issues"""
        self.mySetupStep()
        # we don't really want the test to wait...
        self.step.mirror_sync_sleep = 0.001
        self.build.setProperty("repo_download",
                               "repo download test/bla 564/12", "test")
        self.expectnoClobber()
        self.expectRepoSync()
        self.expectCommands(
            self.ExpectShell(
                command=['repo', 'download', 'test/bla', '564/12'])
            + 1 +
            Expect.log(
                "stdio", stderr="fatal: Couldn't find remote ref \n"),
            self.ExpectShell(
                command=['repo', 'download', 'test/bla', '564/12'])
            + 1 +
            Expect.log(
                "stdio", stderr="fatal: Couldn't find remote ref \n"),
            self.ExpectShell(
                command=['repo', 'download', 'test/bla', '564/12'])
            + 0)
        return self.myRunStep()

    def test_repo_downloads_change_missing(self):
        """repo downloads, with no actual mirror synchronization issues (still retries 2 times)"""
        self.mySetupStep()
        # we don't really want the test to wait...
        self.step.mirror_sync_sleep = 0.001
        self.step.mirror_sync_retry = 1  # on retry once
        self.build.setProperty("repo_download",
                               "repo download test/bla 564/12", "test")
        self.expectnoClobber()
        self.expectRepoSync()
        self.expectCommands(
            self.ExpectShell(
                command=['repo', 'download', 'test/bla', '564/12'])
            + 1 +
            Expect.log(
                "stdio", stderr="fatal: Couldn't find remote ref \n"),
            self.ExpectShell(
                command=['repo', 'download', 'test/bla', '564/12'])
            + 1 +
            Expect.log(
                "stdio", stderr="fatal: Couldn't find remote ref \n"),
        )
        return self.myRunStep(result=FAILURE,
                              state_string="repo: change test/bla 564/12 does not exist (failure)")

    def test_repo_downloads_fail1(self):
        """repo downloads, cherry-pick returns 1"""
        self.mySetupStep()
        self.build.setProperty("repo_download",
                               "repo download test/bla 564/12", "test")
        self.expectnoClobber()
        self.expectRepoSync()
        self.expectCommands(
            self.ExpectShell(
                command=['repo', 'download', 'test/bla', '564/12'])
            + 1 + Expect.log("stdio", stderr="patch \n"),
            self.ExpectShell(
                command=['repo', 'forall', '-c', 'git', 'diff', 'HEAD'])
            + 0
        )
        return self.myRunStep(result=FAILURE,
                              state_string="download failed: test/bla 564/12 (failure)")

    def test_repo_downloads_fail2(self):
        """repo downloads, cherry-pick returns 0 but error in stderr"""
        self.mySetupStep()
        self.build.setProperty("repo_download",
                               "repo download test/bla 564/12", "test")
        self.expectnoClobber()
        self.expectRepoSync()
        self.expectCommands(
            self.ExpectShell(
                command=['repo', 'download', 'test/bla', '564/12'])
            + 0 +
            Expect.log("stdio", stderr="Automatic cherry-pick failed \n"),
            self.ExpectShell(
                command=['repo', 'forall', '-c', 'git', 'diff', 'HEAD'])
            + 0
        )
        return self.myRunStep(result=FAILURE,
                              state_string="download failed: test/bla 564/12 (failure)")

    def test_repo_downloads_from_change_source(self):
        """basic repo download from change source, and check that repo_downloaded is updated"""
        self.mySetupStep(repoDownloads=repo.RepoDownloadsFromChangeSource())
        chdict = TestGerritChangeSource.expected_change
        change = Change(None, None, None, properties=chdict['properties'])
        self.build.allChanges = lambda x=None: [change]
        self.expectnoClobber()
        self.expectRepoSync()
        self.expectCommands(
            self.ExpectShell(command=['repo', 'download', 'pr', '4321/12'])
            + 0
            + Expect.log(
                'stdio', stderr="test/bla refs/changes/64/564/12 -> FETCH_HEAD\n")
            + Expect.log('stdio', stderr="HEAD is now at 0123456789abcdef...\n"))
        self.expectProperty(
            "repo_downloaded", "564/12 0123456789abcdef ", "Source")
        return self.myRunStep()

    def test_repo_downloads_from_change_source_codebase(self):
        """basic repo download from change source, and check that repo_downloaded is updated"""
        self.mySetupStep(
            repoDownloads=repo.RepoDownloadsFromChangeSource("mycodebase"))
        chdict = TestGerritChangeSource.expected_change
        change = Change(None, None, None, properties=chdict['properties'])
        # getSourceStamp is faked by SourceStepMixin
        ss = self.build.getSourceStamp("")
        ss.changes = [change]
        self.expectnoClobber()
        self.expectRepoSync()
        self.expectCommands(
            self.ExpectShell(command=['repo', 'download', 'pr', '4321/12'])
            + 0
            + Expect.log(
                'stdio', stderr="test/bla refs/changes/64/564/12 -> FETCH_HEAD\n")
            + Expect.log('stdio', stderr="HEAD is now at 0123456789abcdef...\n"))
        self.expectProperty(
            "repo_downloaded", "564/12 0123456789abcdef ", "Source")
        return self.myRunStep()

    def test_update_fail1(self):
        """ fail at cleanup: ignored"""
        self.mySetupStep()
        self.expectnoClobber()
        self.expectRepoSync(which_fail=0, breakatfail=False)
        return self.myRunStep()

    def test_update_fail2(self):
        """fail at repo init: clobber"""
        self.mySetupStep()
        self.expectnoClobber()
        self.expectRepoSync(which_fail=1, breakatfail=True)
        self.expectClobber()
        self.expectRepoSync()
        self.shouldRetry = True
        return self.myRunStep()

    def test_update_fail3(self):
        """ fail at repo sync: clobber"""
        self.mySetupStep()
        self.expectnoClobber()
        self.expectRepoSync(which_fail=2, breakatfail=True)
        self.expectClobber()
        self.expectRepoSync()
        self.shouldRetry = True
        return self.myRunStep()

    def test_update_fail4(self):
        """fail at repo manifest: clobber"""
        self.mySetupStep()
        self.expectnoClobber()
        self.expectRepoSync(which_fail=3, breakatfail=True)
        self.expectClobber()
        self.expectRepoSync()
        self.shouldRetry = True
        return self.myRunStep()

    def test_update_doublefail(self):
        """fail at repo manifest: clobber but still fail"""
        self.mySetupStep()
        self.expectnoClobber()
        self.expectRepoSync(which_fail=3, breakatfail=True)
        self.expectClobber()
        self.expectRepoSync(which_fail=3, breakatfail=True)
        self.shouldRetry = True
        return self.myRunStep(result=FAILURE,
                              state_string="repo failed at: repo manifest (failure)")

    def test_update_doublefail2(self):
        """fail at repo sync: clobber but still fail"""
        self.mySetupStep()
        self.expectnoClobber()
        self.expectRepoSync(which_fail=2, breakatfail=True)
        self.expectClobber()
        self.expectRepoSync(which_fail=2, breakatfail=True)
        self.shouldRetry = True
        return self.myRunStep(result=FAILURE,
                              state_string="repo failed at: repo sync (failure)")

    def test_update_doublefail3(self):
        """fail at repo init: clobber but still fail"""
        self.mySetupStep()
        self.expectnoClobber()
        self.expectRepoSync(which_fail=1, breakatfail=True)
        self.expectClobber()
        self.expectRepoSync(which_fail=1, breakatfail=True)
        self.shouldRetry = True
        return self.myRunStep(result=FAILURE,
                              state_string="repo failed at: repo init (failure)")

    def test_basic_fail(self):
        """fail at repo init: no need to re-clobber but still fail"""
        self.mySetupStep()
        self.expectClobber()
        self.expectRepoSync(which_fail=1, breakatfail=True)
        self.shouldRetry = True
        return self.myRunStep(result=FAILURE,
                              state_string="repo failed at: repo init (failure)")
