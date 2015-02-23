from twisted.trial import unittest
from buildbot.test.fake import fakemaster
from buildbot.status import builder
from buildbot.config import ProjectConfig
from mock import Mock
from buildbot.status.build import BuildStatus
from buildbot.status.results import SUCCESS
import datetime

class TestBuilderStatus(unittest.TestCase):

    def test_generateFinishedBuildsUseLatestBuildCache(self):
        m = fakemaster.make_master()
        b = builder.BuilderStatus(buildername="builder-01", category=None,
                                    master=m)

        codebases = {'katana-buildbot': 'katana'}

        katana = {'katana-buildbot':
                      {'project': 'general',
                       'display_name': 'Katana buildbot',
                       'defaultbranch': 'katana',
                       'repository': 'https://github.com/Unity-Technologies/buildbot.git',
                       'display_repository': 'https://github.com/Unity-Technologies/buildbot.git',
                       'branch': ['master', 'staging', 'katana']}}

        self.project = ProjectConfig(name="Katana", codebases=[katana])

        m.getProject = lambda x: self.project
        m.getProjects = lambda: {'Katana': self.project}
        b.nextBuildNumber = 39

        b.latestBuildCache['katana-buildbot=katana;'] = {'date': datetime.datetime.now(), 'build': 38}
        b.buildCache = Mock()

        def getCachedBuild(number):
            build_status = BuildStatus(b, m, number)
            build_status.finished = 1422441501.21
            build_status.reason ='A build was forced by user@localhost'
            build_status.slavename = 'build-slave-01'
            build_status.results = SUCCESS
            return build_status

        b.buildCache.get = getCachedBuild

        builds = list(b.generateFinishedBuilds(branches=[],
                                                     codebases=codebases,
                                                     num_builds=1, max_search=200, useCache=True))

        self.assertTrue(len(builds) > 0)
        self.assertTrue(isinstance(builds[0], BuildStatus))
        self.assertTrue(builds[0].number, 38)
