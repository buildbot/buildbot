# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.

from __future__ import annotations

import datetime
import hashlib
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.config import BuilderConfig
from buildbot.plugins import schedulers
from buildbot.process.factory import BuildFactory
from buildbot.process.results import FAILURE
from buildbot.process.results import SUCCESS
from buildbot.steps.source.git import Git
from buildbot.test.util.git_repository import TestGitRepository
from buildbot.test.util.integration import RunMasterBase

if TYPE_CHECKING:
    from buildbot.util.twisted import InlineCallbacksType


class GitSharedCacheIntegrationTest(RunMasterBase):
    timeout = 120

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        # git canonicalizes symlinked segments (macOS /var -> /private/var)
        temporary_root = Path(tempfile.mkdtemp(prefix='bb-git-cache-')).resolve()
        self.addCleanup(shutil.rmtree, temporary_root, True)
        temporary_index = 0

        def short_mktemp() -> str:
            nonlocal temporary_index
            temporary_index += 1
            return str(temporary_root / str(temporary_index))

        self.patch(self, 'mktemp', short_mktemp)

        try:
            self.repo = TestGitRepository(self.mktemp())
        except FileNotFoundError as e:
            raise unittest.SkipTest("Can't find git binary") from e

        self.repo.create_file_text('tracked.txt', 'first\n')
        self.repo.exec_git(['add', 'tracked.txt'])
        self.first_revision = self.repo.commit('initial')
        self.repo.exec_git(['tag', 'source-only-tag'])
        self.repo.exec_git(['checkout', '--orphan', 'other'])
        self.repo.exec_git(['rm', '-rf', '.'])
        self.repo.create_file_text('other.txt', 'other branch\n')
        self.repo.exec_git(['add', 'other.txt'])
        self.repo.commit('other branch')
        self.other_blob = self._git_output(
            self.repo.repository_path,
            'rev-parse',
            'other:other.txt',
        )
        self.repo.exec_git(['checkout', 'main'])
        self.repo.exec_git(['checkout', '-b', 'ephemeral'])
        self.repo.advance_time(datetime.timedelta(seconds=1))
        self.repo.amend_file_text('tracked.txt', 'ephemeral\n')
        self.ephemeral_revision = self.repo.commit('ephemeral', files=['tracked.txt'])
        self.repo.exec_git([
            'update-ref',
            'refs/pull/1/merge',
            self.ephemeral_revision,
        ])
        self.repo.exec_git(['checkout', 'main'])
        self.repo.exec_git(['branch', '-D', 'ephemeral'])
        self.repo.exec_git(['config', 'uploadpack.allowFilter', 'true'])
        self.repository = self.repo.repository_path.resolve().as_uri()

        builders = []
        for name in ('cache-a', 'cache-b'):
            factory = BuildFactory()
            factory.addStep(
                Git(
                    repourl=self.repository,
                    mode='full',
                    method='fresh',
                    shared_cache=True,
                    filters=['blob:none'],
                    logEnviron=False,
                )
            )
            builders.append(
                BuilderConfig(
                    name=name,
                    workernames=['local1'],
                    workerbuilddir=f'group/{name}',
                    factory=factory,
                )
            )

        yield self.setup_master({
            'builders': builders,
            'schedulers': [
                schedulers.AnyBranchScheduler(
                    name='shared-cache',
                    builderNames=['cache-a', 'cache-b'],
                )
            ],
        })

    def _change(self, revision: str, branch: str = 'main') -> dict[str, object]:
        return {
            'branch': branch,
            'files': ['tracked.txt'],
            'author': 'test@example.com',
            'comments': 'shared cache integration test',
            'revision': revision,
            'repository': self.repository,
            'project': 'test',
        }

    def _git_output(self, repository: Path, *args: str) -> str:
        return subprocess.check_output(
            ['git', *args],
            cwd=repository,
            text=True,
        ).strip()

    @defer.inlineCallbacks
    def test_existing_linked_worktree_uses_common_object_directory(
        self,
    ) -> InlineCallbacksType[None]:
        first_build = yield self.doForceBuild(
            wantSteps=True, useChange=self._change(self.first_revision)
        )
        self.assertEqual(first_build['results'], SUCCESS)

        worker = self.master.workers.getWorkerByName('local1')
        worker_basedir = Path(worker.worker_basedir)
        cache_hash = hashlib.sha256(self.repository.encode('utf-8')).hexdigest()[:16]
        cache_path = worker_basedir / '.git-cache' / f'{cache_hash}.git'
        checkout_path = worker_basedir / 'group' / 'cache-a' / 'build'

        shutil.rmtree(checkout_path)
        subprocess.check_call(
            ['git', 'worktree', 'add', '--detach', str(checkout_path), self.first_revision],
            cwd=self.repo.repository_path,
        )
        self.assertTrue((checkout_path / '.git').is_file())

        second_build = yield self.doForceBuild(
            wantSteps=True, useChange=self._change(self.first_revision)
        )
        self.assertEqual(second_build['results'], SUCCESS)

        common_info = Path(
            self._git_output(checkout_path, 'rev-parse', '--git-path', 'objects/info')
        )
        self.assertEqual(
            (common_info / 'alternates').read_text().strip(),
            (cache_path / 'objects').as_posix(),
        )
        self.assertEqual(
            (common_info / 'buildbot-shared-cache').read_text().strip(),
            (cache_path / 'objects').as_posix(),
        )

    @defer.inlineCallbacks
    def test_builders_share_cache_and_update_existing_repositories(
        self,
    ) -> InlineCallbacksType[None]:
        first_build = yield self.doForceBuild(
            wantSteps=True, useChange=self._change(self.first_revision)
        )
        self.assertEqual(first_build['results'], SUCCESS)

        worker = self.master.workers.getWorkerByName('local1')
        worker_basedir = Path(worker.worker_basedir)
        cache_hash = hashlib.sha256(self.repository.encode('utf-8')).hexdigest()[:16]
        cache_path = worker_basedir / '.git-cache' / f'{cache_hash}.git'
        cache_objects = (cache_path / 'objects').as_posix()

        self.assertEqual(self._git_output(cache_path, 'rev-parse', '--is-bare-repository'), 'true')
        self.assertEqual(self._git_output(cache_path, 'config', '--get', 'gc.auto'), '0')
        self.assertEqual(
            self._git_output(cache_path, 'config', '--get', 'maintenance.auto'),
            'false',
        )
        self.assertEqual(
            self._git_output(cache_path, 'config', '--get', 'buildbot.sharedCacheIdentity'),
            self.repository,
        )
        self.assertGreater(
            int(self._git_output(cache_path, 'config', '--get', 'buildbot.sharedCacheLastFsck')),
            0,
        )
        self.assertEqual(self._git_output(cache_path, 'cat-file', '-t', self.other_blob), 'blob')
        cache_tags = self._git_output(
            cache_path,
            'for-each-ref',
            '--format=%(refname)',
            'refs/tags',
        ).splitlines()
        self.assertNotIn('refs/tags/source-only-tag', cache_tags)
        self._git_output(
            cache_path,
            'update-ref',
            'refs/custom/preserved',
            self.first_revision,
        )

        checkout_paths = [
            worker_basedir / 'group' / builder / 'build' for builder in ('cache-a', 'cache-b')
        ]
        for checkout_path in checkout_paths:
            self.assertEqual((checkout_path / 'tracked.txt').read_text(), 'first\n')
            self.assertEqual(
                (checkout_path / '.git' / 'objects' / 'info' / 'alternates').read_text().strip(),
                cache_objects,
            )
            self.assertEqual(
                self._git_output(checkout_path, 'config', '--get', 'remote.origin.promisor'),
                'true',
            )
            counts = dict(
                line.split(': ', 1)
                for line in self._git_output(checkout_path, 'count-objects', '-v').splitlines()
                if ': ' in line
            )
            self.assertEqual(int(counts['count']), 0)
            self.assertEqual(int(counts['in-pack']), 0)

        ephemeral_build = yield self.doForceBuild(
            wantSteps=True,
            useChange=self._change(
                self.ephemeral_revision,
                branch='refs/pull/1/merge',
            ),
        )
        self.assertEqual(ephemeral_build['results'], SUCCESS)
        self.assertEqual(
            self._git_output(cache_path, 'cat-file', '-t', self.ephemeral_revision),
            'commit',
        )
        self.assertIn(self.ephemeral_revision, (cache_path / 'FETCH_HEAD').read_text())

        buildbot_refs = self._git_output(
            cache_path,
            'for-each-ref',
            '--format=%(refname)',
            'refs/buildbot',
        ).splitlines()
        self.assertEqual(buildbot_refs, [])
        requested_refs = self._git_output(
            cache_path,
            'for-each-ref',
            '--format=%(refname)',
            'refs/pull',
        ).splitlines()
        self.assertEqual(requested_refs, [])

        self.repo.advance_time(datetime.timedelta(seconds=1))
        self.repo.amend_file_text('tracked.txt', 'second\n')
        second_revision = self.repo.commit('second', files=['tracked.txt'])

        second_build = yield self.doForceBuild(
            wantSteps=True,
            useChange=self._change(second_revision),
        )
        self.assertEqual(second_build['results'], SUCCESS)

        for checkout_path in checkout_paths:
            self.assertEqual((checkout_path / 'tracked.txt').read_text(), 'first\nsecond\n')
            self.assertEqual(self._git_output(checkout_path, 'rev-parse', 'HEAD'), second_revision)
        self.assertEqual(
            self._git_output(cache_path, 'rev-parse', 'refs/custom/preserved'),
            self.first_revision,
        )

        self._git_output(cache_path, 'gc')
        cache_only_blob = subprocess.check_output(
            ['git', 'hash-object', '-w', '--stdin'],
            cwd=cache_path,
            input='cache only\n',
            text=True,
        ).strip()
        for checkout_path in checkout_paths:
            self._git_output(
                checkout_path,
                'update-ref',
                'refs/buildbot-test/cache-only',
                cache_only_blob,
            )
        preservation_marker = cache_path / 'buildbot-preserve-corrupt-cache'
        preservation_marker.write_text('preserve\n')
        cache_pack = next((cache_path / 'objects' / 'pack').glob('*.pack'))
        cache_pack.chmod(0o600)
        with cache_pack.open('r+b') as pack_file:
            pack_file.truncate(32)
        self._git_output(
            cache_path,
            'config',
            'buildbot.sharedCacheLastFsck',
            '0',
        )

        corrupted_build = yield self.doForceBuild(
            wantSteps=True,
            useChange=self._change(second_revision),
        )
        self.assertIn(corrupted_build['results'], (SUCCESS, FAILURE))
        self.assertTrue(preservation_marker.is_file())
        with self.assertRaises(subprocess.CalledProcessError):
            self._git_output(cache_path, 'fsck', '--no-dangling')

        for checkout_path in checkout_paths:
            self.assertEqual(self._git_output(checkout_path, 'rev-parse', 'HEAD'), second_revision)
            self.assertEqual(
                self._git_output(checkout_path, 'cat-file', '-p', cache_only_blob),
                'cache only',
            )


SHARED_CACHE_ROOT_ENV = 'BUILDBOT_TEST_GIT_SHARED_CACHE_ROOT'
SHARED_CACHE_SOURCE_ROOT_ENV = 'BUILDBOT_TEST_GIT_SHARED_CACHE_SOURCE_ROOT'

# GIT_CONFIG_* confines this trust to the test subprocesses
GIT_TRUST_ENV = {
    'GIT_CONFIG_COUNT': '1',
    'GIT_CONFIG_KEY_0': 'safe.directory',
    'GIT_CONFIG_VALUE_0': '*',
}


class GitSharedCacheNetworkPathTest(RunMasterBase):
    r"""Shared cache on a network path, skipped unless one is configured.

    ``BUILDBOT_TEST_GIT_SHARED_CACHE_ROOT`` holds the cache: a UNC path such as
    ``\\server\share``, a mapped drive such as ``Z:\``, or any remote mount.
    ``BUILDBOT_TEST_GIT_SHARED_CACHE_SOURCE_ROOT`` optionally hosts the origin
    repository, making ``repourl`` a network path too.
    """

    timeout = 240

    @defer.inlineCallbacks
    def setUp(self) -> InlineCallbacksType[None]:  # type: ignore[override]
        cache_root = os.environ.get(SHARED_CACHE_ROOT_ENV)
        if not cache_root:
            raise unittest.SkipTest(f'{SHARED_CACHE_ROOT_ENV} is not set')

        temporary_root = Path(tempfile.mkdtemp(prefix='bb-git-net-')).resolve()
        self.addCleanup(shutil.rmtree, temporary_root, True)
        temporary_index = 0

        def short_mktemp() -> str:
            nonlocal temporary_index
            temporary_index += 1
            return str(temporary_root / str(temporary_index))

        self.patch(self, 'mktemp', short_mktemp)

        # only the parent may exist: Buildbot must create the cache itself
        cache_holder = tempfile.mkdtemp(prefix='bb-cache-', dir=cache_root)
        self.addCleanup(shutil.rmtree, cache_holder, True)
        self.cache_path = os.path.join(cache_holder, 'shared-cache.git')

        source_root = os.environ.get(SHARED_CACHE_SOURCE_ROOT_ENV)
        if source_root:
            source_holder = tempfile.mkdtemp(prefix='bb-src-', dir=source_root)
            self.addCleanup(shutil.rmtree, source_holder, True)
            source_path = os.path.join(source_holder, 'origin')
        else:
            source_path = self.mktemp()

        try:
            self.repo = TestGitRepository(source_path)
        except FileNotFoundError as e:
            raise unittest.SkipTest("Can't find git binary") from e

        self.repo.create_file_text('tracked.txt', 'first\n')
        self.repo.exec_git(['add', 'tracked.txt'], env=GIT_TRUST_ENV)
        self.first_revision = self.repo.commit('initial', env=GIT_TRUST_ENV)
        self.repo.exec_git(['config', 'uploadpack.allowFilter', 'true'], env=GIT_TRUST_ENV)

        # a plain path, not a file:// URL, to exercise worker path handling
        if source_root:
            self.repository = str(self.repo.repository_path)
        else:
            self.repository = self.repo.repository_path.resolve().as_uri()

        builders = []
        for name in ('net-a', 'net-b'):
            factory = BuildFactory()
            factory.addStep(
                Git(
                    repourl=self.repository,
                    mode='full',
                    method='fresh',
                    shared_cache=self.cache_path,
                    filters=['blob:none'],
                    logEnviron=False,
                )
            )
            builders.append(
                BuilderConfig(
                    name=name,
                    workernames=['local1'],
                    workerbuilddir=f'group/{name}',
                    factory=factory,
                )
            )

        yield self.setup_master({
            'builders': builders,
            'schedulers': [
                schedulers.AnyBranchScheduler(
                    name='shared-cache-network',
                    builderNames=['net-a', 'net-b'],
                )
            ],
        })

    def _change(self, revision: str, branch: str = 'main') -> dict[str, object]:
        return {
            'branch': branch,
            'files': ['tracked.txt'],
            'author': 'test@example.com',
            'comments': 'shared cache network path test',
            'revision': revision,
            'repository': self.repository,
            'project': 'test',
        }

    def _git_output(self, repository: str | Path, *args: str) -> str:
        return subprocess.check_output(
            ['git', *args],
            cwd=repository,
            text=True,
            env={**os.environ, **GIT_TRUST_ENV},
        ).strip()

    def _git_config(self, repository: str | Path, key: str) -> str:
        """Read a config value, returning '' when the key is unset."""
        result = subprocess.run(
            ['git', 'config', '--get', key],
            cwd=repository,
            text=True,
            capture_output=True,
            check=False,
            env={**os.environ, **GIT_TRUST_ENV},
        )
        return result.stdout.strip()

    @defer.inlineCallbacks
    def test_network_path_cache_is_created_and_updated(self) -> InlineCallbacksType[None]:
        first_build = yield self.doForceBuild(
            wantSteps=True, useChange=self._change(self.first_revision)
        )
        self.assertEqual(first_build['results'], SUCCESS)

        self.assertEqual(
            self._git_output(self.cache_path, 'rev-parse', '--is-bare-repository'),
            'true',
        )
        self.assertEqual(
            self._git_config(self.cache_path, 'buildbot.sharedCacheOwner'),
            self.repository,
        )
        self.assertEqual(
            self._git_config(self.cache_path, 'buildbot.sharedCacheIdentity'),
            self.repository,
        )
        # the checkout is filtered; the cache must stay full
        self.assertEqual(self._git_config(self.cache_path, 'remote.origin.promisor'), '')

        expected_alternate = os.path.join(self.cache_path, 'objects').replace('\\', '/')
        worker_basedir = Path(self.master.workers.getWorkerByName('local1').worker_basedir)
        checkout_paths = [
            worker_basedir / 'group' / builder / 'build' for builder in ('net-a', 'net-b')
        ]

        for checkout_path in checkout_paths:
            self.assertEqual((checkout_path / 'tracked.txt').read_text(), 'first\n')
            info_dir = checkout_path / '.git' / 'objects' / 'info'
            self.assertIn(
                expected_alternate,
                (info_dir / 'alternates').read_text().splitlines(),
            )
            self.assertEqual(
                (info_dir / 'buildbot-shared-cache').read_text().strip(),
                expected_alternate,
            )
            self.assertEqual(
                self._git_config(checkout_path, 'remote.origin.promisor'),
                'true',
            )

        self.assertFalse((worker_basedir / '.git-cache').exists())

        self.repo.advance_time(datetime.timedelta(seconds=1))
        self.repo.amend_file_text('tracked.txt', 'second\n')
        second_revision = self.repo.commit('second', files=['tracked.txt'], env=GIT_TRUST_ENV)

        second_build = yield self.doForceBuild(
            wantSteps=True, useChange=self._change(second_revision)
        )
        self.assertEqual(second_build['results'], SUCCESS)

        for checkout_path in checkout_paths:
            self.assertEqual((checkout_path / 'tracked.txt').read_text(), 'first\nsecond\n')
            self.assertEqual(
                self._git_output(checkout_path, 'rev-parse', 'HEAD'),
                second_revision,
            )
            self.assertIn(
                expected_alternate,
                (checkout_path / '.git' / 'objects' / 'info' / 'alternates')
                .read_text()
                .splitlines(),
            )

        self.assertEqual(
            self._git_output(self.cache_path, 'rev-parse', 'refs/heads/main'),
            second_revision,
        )
