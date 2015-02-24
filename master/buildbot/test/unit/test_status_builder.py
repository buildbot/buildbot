from twisted.trial import unittest
from buildbot.test.fake import fakemaster
from buildbot.status import builder
from buildbot.config import ProjectConfig
from mock import Mock
from buildbot.status.build import BuildStatus
from buildbot.status.results import SUCCESS
import datetime

class TestBuilderStatus(unittest.TestCase):

    def setUp(self):
        self.master = fakemaster.make_master()

        katana = {'katana-buildbot':
                      {'project': 'general',
                       'display_name': 'Katana buildbot',
                       'defaultbranch': 'katana',
                       'repository': 'https://github.com/Unity-Technologies/buildbot.git',
                       'display_repository': 'https://github.com/Unity-Technologies/buildbot.git',
                       'branch': ['master', 'staging', 'katana']}}

        self.project = ProjectConfig(name="Katana", codebases=[katana])

        self.master.getProject = lambda x: self.project
        self.getProjects = lambda: {'Katana': self.project}

        self.builder_status = builder.BuilderStatus(buildername="builder-01", category=None,
                                    master=self.master)

        self.builder_status.nextBuildNumber = 39

        self.builder_status.buildCache = Mock()

        def getCachedBuild(number):
            build_status = BuildStatus(self.builder_status, self.master, number)
            build_status.finished = 1422441501.21
            build_status.reason ='A build was forced by user@localhost'
            build_status.slavename = 'build-slave-01'
            build_status.results = SUCCESS
            return build_status

        self.builder_status.buildCache.get = getCachedBuild

    def test_generateFinishedBuildsUseLatestBuildCache(self):

        codebases = {'katana-buildbot': 'katana'}

        self.builder_status.latestBuildCache['katana-buildbot=katana;'] = {'date': datetime.datetime.now(),
                                                                           'build': 38}

        builds = list(self.builder_status.generateFinishedBuilds(branches=[],
                                                     codebases=codebases,
                                                     num_builds=1, max_search=200, useCache=True))

        self.assertTrue(len(builds) > 0)
        self.assertTrue(isinstance(builds[0], BuildStatus))
        self.assertTrue(builds[0].number, 38)


    def test_generateFinishedBuildsUseBuildCache(self):

        codebases = {'katana-buildbot': 'katana'}

        self.builder_status.saveYourself = lambda skipBuilds: True

        self.assertEqual(self.builder_status.latestBuildCache, {})

        builds = list(self.builder_status.generateFinishedBuilds(branches=[],
                                                     codebases=codebases,
                                                     num_builds=1, max_search=200, useCache=True))

        self.assertTrue('katana-buildbot=katana;' in self.builder_status.latestBuildCache.keys())
        self.assertTrue(self.builder_status.latestBuildCache['katana-buildbot=katana;']['build'], 38)
        self.assertTrue(len(builds) > 0)
        self.assertTrue(isinstance(builds[0], BuildStatus))
        self.assertTrue(builds[0].number, 38)
