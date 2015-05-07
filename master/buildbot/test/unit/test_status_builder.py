from twisted.trial import unittest
from buildbot.test.fake import fakemaster
from buildbot.status import builder
from buildbot.config import ProjectConfig
from mock import Mock
from buildbot.status.build import BuildStatus
from buildbot.status.results import SUCCESS
from buildbot.sourcestamp import SourceStamp
from twisted.internet import defer

import datetime

class TestBuilderStatus(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master(wantDb=True, testcase="TestBuilderStatus")

        katana = {'katana-buildbot':
                      {'project': 'general',
                       'display_name': 'Katana buildbot',
                       'defaultbranch': 'katana',
                       'repository': 'https://github.com/Unity-Technologies/buildbot.git',
                       'display_repository': 'https://github.com/Unity-Technologies/buildbot.git',
                       'branch': ['katana', 'master', 'staging']}}

        self.project = ProjectConfig(name="Katana", codebases=[katana])

        self.master.getProject = lambda x: self.project
        self.getProjects = lambda: {'Katana': self.project}

        self.master.db.builds.getLastBuildsNumbers = lambda buildername, sourcestamps, num_builds: defer.succeed([38])

        self.builder_status = builder.BuilderStatus(buildername="builder-01", category=None,
                                    master=self.master)

        self.builder_status.nextBuildNumber = 39
        self.builder_status.master = self.master

        self.builder_status.buildCache = Mock()

        def getCachedBuild(number):
            build_status = BuildStatus(self.builder_status, self.master, number)
            build_status.finished = 1422441501.21
            build_status.reason ='A build was forced by user@localhost'
            build_status.slavename = 'build-slave-01'
            build_status.results = SUCCESS
            build_status.sources = [SourceStamp(branch='katana',
                                                codebase='katana-buildbot',
                                                revision='804d540eac7b90022130d34616a8f8336fe5691a')]
            return build_status

        self.builder_status.buildCache.get = getCachedBuild

        self.builder_status.saveYourself = lambda skipBuilds: True

    @defer.inlineCallbacks
    def test_generateFinishedBuildsUseLatestBuildCache(self):

        codebases = {'katana-buildbot': 'katana'}

        self.builder_status.latestBuildCache['katana-buildbot=katana;'] = {'date': datetime.datetime.now(),
                                                                           'build': 38}

        builds = yield self.builder_status.generateFinishedBuildsAsync(branches=[],
                                                                       codebases=codebases,
                                                                       num_builds=1, max_search=200,
                                                                       useCache=True)

        self.assertTrue(len(builds) > 0)
        self.assertTrue(isinstance(builds[0], BuildStatus))
        self.assertEqual(builds[0].number, 38)

    @defer.inlineCallbacks
    def test_generateFinishedBuildsUseBuildCache(self):

        codebases = {'katana-buildbot': 'katana'}

        self.assertEqual(self.builder_status.latestBuildCache, {})

        builds = yield self.builder_status.generateFinishedBuildsAsync(branches=[],
                                                                       codebases=codebases,
                                                                       num_builds=1,
                                                                       max_search=200,
                                                                       useCache=True)

        self.assertTrue('katana-buildbot=katana;' in self.builder_status.latestBuildCache.keys())
        self.assertEqual(self.builder_status.latestBuildCache['katana-buildbot=katana;']['build'], 38)
        self.assertTrue(len(builds) > 0)
        self.assertTrue(isinstance(builds[0], BuildStatus))
        self.assertEqual(builds[0].number, 38)


    @defer.inlineCallbacks
    def test_emptyCodebaseSelectionShouldSkipLatestBuildCache(self):
        codebases = {}

        self.assertEqual(self.builder_status.latestBuildCache, {})

        builds = yield self.builder_status.generateFinishedBuildsAsync(branches=[],
                                                     codebases=codebases,
                                                     num_builds=1, useCache=True)

        self.assertEqual(self.builder_status.latestBuildCache, {})
        self.assertTrue(len(builds) > 0)
        self.assertTrue(isinstance(builds[0], BuildStatus))
        self.assertEqual(builds[0].number, 38)

    @defer.inlineCallbacks
    def test_generateFinishedBuildsUpdateToProjectCodebases(self):

        codebases = {'codebase1': 'branch1', 'codebase2': 'branch2'}

        self.master.db.builds.getLastBuildsNumbers = lambda buildername, sourcestamps, num_builds: defer.succeed([])

        self.assertEqual(self.builder_status.latestBuildCache, {})

        builds = yield self.builder_status.generateFinishedBuildsAsync(branches=[],
                                                     codebases=codebases,
                                                     num_builds=1, useCache=True)

        self.assertEqual(self.builder_status.latestBuildCache['katana-buildbot=katana;']['build'], None)


    def multipleCodebasesProject(self):
        cb1 = {'codebase1': {'defaultbranch': 'branch1',
                             'repository': 'https://github.com/Unity-Technologies/buildbot.git',
                             'branch': ['branch1', 'branch1.1']}}
        cb2 = {'codebase2': {'defaultbranch': 'branch2',
                             'repository': 'https://github.com/Unity-Technologies/buildbot.git',
                             'branch': ['branch2', 'branch2.1']}}
        self.project = ProjectConfig(name="Katana", codebases=[cb1, cb2])
        self.master.getProject = lambda x: self.project
        self.getProjects = lambda: {'Katana': self.project}

    @defer.inlineCallbacks
    def test_generateFinishedBuildsMultipleCodebasesSkipCache(self):
        self.multipleCodebasesProject()
        codebases = {'codebase1': 'branch1', 'codebase2': 'branch2'}

        self.master.db.builds.getLastBuildsNumbers = lambda buildername, sourcestamps, num_builds: defer.succeed([])

        self.assertEqual(self.builder_status.latestBuildCache, {})

        yield self.builder_status.generateFinishedBuildsAsync(branches=[],
                                                     codebases=codebases,
                                                     num_builds=1, useCache=True)

        self.assertEqual(self.builder_status.latestBuildCache, {})

    @defer.inlineCallbacks
    def test_generateFinishedBuildsMultipleCodebasesSaveCache(self):
        self.multipleCodebasesProject()
        codebases = {'codebase1': 'branch1'}

        self.assertEqual(self.builder_status.latestBuildCache, {})

        yield self.builder_status.generateFinishedBuildsAsync(branches=[],
                                                     codebases=codebases,
                                                     num_builds=1, useCache=True)

        self.assertEqual(self.builder_status.latestBuildCache['codebase1=branch1;codebase2=branch2;']['build'], 38)
