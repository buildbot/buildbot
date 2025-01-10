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

import os
import tempfile

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.config import BuilderConfig
from buildbot.plugins import changes
from buildbot.plugins import schedulers
from buildbot.process import factory
from buildbot.steps.configurable import BuildbotCiSetupSteps
from buildbot.steps.configurable import BuildbotTestCiTrigger
from buildbot.steps.source.git import Git
from buildbot.test.util.git_repository import TestGitRepository
from buildbot.test.util.integration import RunMasterBase
from buildbot.worker import Worker

buildbot_ci_yml = """\
language: python

label_mapping:
  TWISTED: tw
  SQLALCHEMY: sqla
  SQLALCHEMY_MIGRATE: sqlam
  latest: l
  python: py

python:
  - "3.9"
env:
  global:
      - CI=true
matrix:
  include:
    # Test different versions of SQLAlchemy
    - python: "3.9"
      env: TWISTED=12.0.0 SQLALCHEMY=0.6.0 SQLALCHEMY_MIGRATE=0.7.1
    - python: "3.9"
      env: TWISTED=13.0.0 SQLALCHEMY=0.6.8 SQLALCHEMY_MIGRATE=0.7.1
    - python: "3.9"
      env: TWISTED=14.0.0 SQLALCHEMY=0.6.8 SQLALCHEMY_MIGRATE=0.7.1
    - python: "3.9"
      env: TWISTED=15.0.0 SQLALCHEMY=0.6.8 SQLALCHEMY_MIGRATE=0.7.1

before_install:
  - echo doing before install
  - echo doing before install 2nd command
install:
  - echo doing install
script:
  - echo doing scripts
  - echo Ran 10 tests with 0 failures and 0 errors
after_success:
  - echo doing after success
notifications:
  email: false

"""


class BuildbotTestCiTest(RunMasterBase):
    timeout = 300

    @defer.inlineCallbacks
    def setUp(self):
        yield super().setUp()
        try:
            self.repo = TestGitRepository(
                repository_path=tempfile.mkdtemp(
                    prefix="TestRepository_",
                    dir=os.getcwd(),
                )
            )
        except FileNotFoundError as e:
            raise unittest.SkipTest("Can't find git binary") from e

        self.prepare_repository()

    def prepare_repository(self):
        self.repo.create_file_text('.bbtravis.yml', buildbot_ci_yml)
        self.repo.exec_git(['add', '.bbtravis.yml'])
        self.repo.commit(message='Initial commit', files=['.bbtravis.yml'])

    @defer.inlineCallbacks
    def setup_config(self):
        c = {
            'workers': [Worker("local1", "p")],
            'services': [
                changes.GitPoller(
                    repourl=str(self.repo.repository_path), project='buildbot', branch='main'
                )
            ],
            'builders': [],
            'schedulers': [],
            'multiMaster': True,
        }

        repository = str(self.repo.repository_path)
        job_name = "buildbot-job"
        try_name = "buildbot-try"
        spawner_name = "buildbot"

        codebases = {spawner_name: {'repository': repository}}

        # main job
        f = factory.BuildFactory()
        f.addStep(Git(repourl=repository, codebase=spawner_name, mode='incremental'))
        f.addStep(BuildbotCiSetupSteps())

        c['builders'].append(
            BuilderConfig(
                name=job_name,
                workernames=['local1'],
                collapseRequests=False,
                tags=["job", 'buildbot'],
                factory=f,
            )
        )

        c['schedulers'].append(
            schedulers.Triggerable(name=job_name, builderNames=[job_name], codebases=codebases)
        )

        # spawner
        f = factory.BuildFactory()
        f.addStep(Git(repourl=repository, codebase=spawner_name, mode='incremental'))
        f.addStep(BuildbotTestCiTrigger(scheduler=job_name))
        c['builders'].append(
            BuilderConfig(
                name=spawner_name,
                workernames=['local1'],
                properties={'BUILDBOT_PULL_REQUEST': True},
                tags=["spawner", 'buildbot'],
                factory=f,
            )
        )

        c['schedulers'].append(
            schedulers.AnyBranchScheduler(
                name=spawner_name, builderNames=[spawner_name], codebases=codebases
            )
        )

        # try job
        f = factory.BuildFactory()
        f.addStep(Git(repourl=repository, codebase=spawner_name, mode='incremental'))
        f.addStep(BuildbotTestCiTrigger(scheduler=job_name))

        c['builders'].append(
            BuilderConfig(
                name=try_name,
                workernames=['local1'],
                properties={'BUILDBOT_PULL_REQUEST': True},
                tags=["try", 'buildbot'],
                factory=f,
            )
        )

        yield self.setup_master(c)

    @defer.inlineCallbacks
    def test_buildbot_ci(self):
        yield self.setup_config()
        change = dict(
            branch="main",
            files=["foo.c"],
            author="me@foo.com",
            comments="good stuff",
            revision="HEAD",
            repository=str(self.repo.repository_path),
            codebase='buildbot',
            project="buildbot",
        )
        build = yield self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)
        if 'worker local1 ready' in build['steps'][0]['state_string']:
            build['steps'] = build['steps'][1:]
        self.assertEqual(build['steps'][0]['state_string'], 'update buildbot')
        self.assertEqual(build['steps'][0]['name'], 'git-buildbot')
        self.assertEqual(
            build['steps'][1]['state_string'],
            'triggered ' + ", ".join(["buildbot-job"] * 4) + ', 4 successes',
        )
        url_names = [url['name'] for url in build['steps'][1]['urls']]
        url_urls = [url['url'] for url in build['steps'][1]['urls']]
        self.assertIn('http://localhost:8080/#/builders/4/builds/1', url_urls)
        self.assertIn('success: buildbot py:3.9 sqla:0.6.0 sqlam:0.7.1 tw:12.0.0 #1', url_names)
        self.assertEqual(build['steps'][1]['logs'][0]['contents']['content'], buildbot_ci_yml)

        builds = yield self.master.data.get(("builds",))
        self.assertEqual(len(builds), 5)
        props = {}
        buildernames = {}
        labels = {}
        for build in builds:
            build['properties'] = yield self.master.data.get((
                "builds",
                build['buildid'],
                'properties',
            ))
            props[build['buildid']] = {
                k: v[0] for k, v in build['properties'].items() if v[1] == 'BuildbotTestCiTrigger'
            }
            buildernames[build['buildid']] = build['properties'].get('virtual_builder_name')
            labels[build['buildid']] = build['properties'].get('matrix_label')
        self.assertEqual(
            props,
            {
                1: {},
                2: {
                    'python': '3.9',
                    'CI': 'true',
                    'TWISTED': '12.0.0',
                    'SQLALCHEMY': '0.6.0',
                    'SQLALCHEMY_MIGRATE': '0.7.1',
                    'virtual_builder_name': 'buildbot py:3.9 sqla:0.6.0 sqlam:0.7.1 tw:12.0.0',
                    'virtual_builder_tags': [
                        'buildbot',
                        'py:3.9',
                        'sqla:0.6.0',
                        'sqlam:0.7.1',
                        'tw:12.0.0',
                        '_virtual_',
                    ],
                    'matrix_label': 'py:3.9/sqla:0.6.0/sqlam:0.7.1/tw:12.0.0',
                },
                3: {
                    'python': '3.9',
                    'CI': 'true',
                    'TWISTED': '13.0.0',
                    'SQLALCHEMY': '0.6.8',
                    'SQLALCHEMY_MIGRATE': '0.7.1',
                    'virtual_builder_name': 'buildbot py:3.9 sqla:0.6.8 sqlam:0.7.1 tw:13.0.0',
                    'virtual_builder_tags': [
                        'buildbot',
                        'py:3.9',
                        'sqla:0.6.8',
                        'sqlam:0.7.1',
                        'tw:13.0.0',
                        '_virtual_',
                    ],
                    'matrix_label': 'py:3.9/sqla:0.6.8/sqlam:0.7.1/tw:13.0.0',
                },
                4: {
                    'python': '3.9',
                    'CI': 'true',
                    'TWISTED': '14.0.0',
                    'SQLALCHEMY': '0.6.8',
                    'SQLALCHEMY_MIGRATE': '0.7.1',
                    'virtual_builder_name': 'buildbot py:3.9 sqla:0.6.8 sqlam:0.7.1 tw:14.0.0',
                    'virtual_builder_tags': [
                        'buildbot',
                        'py:3.9',
                        'sqla:0.6.8',
                        'sqlam:0.7.1',
                        'tw:14.0.0',
                        '_virtual_',
                    ],
                    'matrix_label': 'py:3.9/sqla:0.6.8/sqlam:0.7.1/tw:14.0.0',
                },
                5: {
                    'python': '3.9',
                    'CI': 'true',
                    'TWISTED': '15.0.0',
                    'SQLALCHEMY': '0.6.8',
                    'SQLALCHEMY_MIGRATE': '0.7.1',
                    'virtual_builder_name': 'buildbot py:3.9 sqla:0.6.8 sqlam:0.7.1 tw:15.0.0',
                    'virtual_builder_tags': [
                        'buildbot',
                        'py:3.9',
                        'sqla:0.6.8',
                        'sqlam:0.7.1',
                        'tw:15.0.0',
                        '_virtual_',
                    ],
                    'matrix_label': 'py:3.9/sqla:0.6.8/sqlam:0.7.1/tw:15.0.0',
                },
            },
        )
        # global env CI should not be there
        self.assertEqual(
            buildernames,
            {
                1: None,
                2: ('buildbot py:3.9 sqla:0.6.0 sqlam:0.7.1 tw:12.0.0', 'BuildbotTestCiTrigger'),
                3: ('buildbot py:3.9 sqla:0.6.8 sqlam:0.7.1 tw:13.0.0', 'BuildbotTestCiTrigger'),
                4: ('buildbot py:3.9 sqla:0.6.8 sqlam:0.7.1 tw:14.0.0', 'BuildbotTestCiTrigger'),
                5: ('buildbot py:3.9 sqla:0.6.8 sqlam:0.7.1 tw:15.0.0', 'BuildbotTestCiTrigger'),
            },
        )
        self.assertEqual(
            labels,
            {
                1: None,
                2: ('py:3.9/sqla:0.6.0/sqlam:0.7.1/tw:12.0.0', 'BuildbotTestCiTrigger'),
                3: ('py:3.9/sqla:0.6.8/sqlam:0.7.1/tw:13.0.0', 'BuildbotTestCiTrigger'),
                4: ('py:3.9/sqla:0.6.8/sqlam:0.7.1/tw:14.0.0', 'BuildbotTestCiTrigger'),
                5: ('py:3.9/sqla:0.6.8/sqlam:0.7.1/tw:15.0.0', 'BuildbotTestCiTrigger'),
            },
        )
