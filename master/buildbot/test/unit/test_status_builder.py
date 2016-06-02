from twisted.trial import unittest
from buildbot.test.fake import fakemaster
from buildbot.status import builder
from buildbot.status import buildrequest
from buildbot.config import ProjectConfig
from mock import Mock
from buildbot.status.build import BuildStatus
from buildbot.status.results import SUCCESS
from buildbot.sourcestamp import SourceStamp
from twisted.internet import defer
from buildbot.status.master import Status
from buildbot.test.fake import fakedb
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

        self.master.db.builds.getLastBuildsNumbers = lambda buildername, sourcestamps, results, num_builds: \
            defer.succeed([38])

        self.builder_status = builder.BuilderStatus(buildername="builder-01", category=None,
                                    master=self.master)

        self.builder_status.nextBuildNumber = 39
        self.builder_status.master = self.master

        self.builder_status.buildCache = Mock()
        self.builder_status.buildCache.cache = {}

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
                                                                       num_builds=1,
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

        self.master.db.builds.getLastBuildsNumbers = lambda buildername, sourcestamps, results, num_builds: \
            defer.succeed([])

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

        self.master.db.builds.getLastBuildsNumbers = lambda buildername, sourcestamps, results, num_builds: \
            defer.succeed([])

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

    @defer.inlineCallbacks
    def setupPendingBuildCache(
            self,
            initialCache={},
            initialDictsCache={}):

        status = Status(self.master)
        self.builder_status.setStatus(status=status)

        self.builder_status.pendingBuildsCache.buildRequestStatusCodebasesCache = initialCache

        self.builder_status.pendingBuildsCache.buildRequestStatusCodebasesDictsCache = initialDictsCache

        row = [
            fakedb.BuildRequest(id=2, buildsetid=2, buildername='builder-01', priority=13, results=-1)
        ]
        yield self.master.db.insertTestData(row)

    def checkPendingBuildsCache(
            self,
            expectedDictsCache={},
            expectedCache={},
            key=''):

        self.assertEquals(
                self.builder_status.pendingBuildsCache.buildRequestStatusCodebasesDictsCache,
                expectedDictsCache)

        if len(expectedCache) > 0:
            self.assertTrue(len(self.builder_status.pendingBuildsCache.buildRequestStatusCodebasesCache[key]),
                            len(expectedCache[key]))
            self.assertEquals(
                    self.builder_status.pendingBuildsCache.buildRequestStatusCodebasesCache[key][0].brid,
                    expectedCache[key][0].brid)

    @defer.inlineCallbacks
    def test_requestSubmittedResetsPendingBuildsCache(self):
        yield self.setupPendingBuildCache(
                initialCache={'codebase=branch': [Mock(brid=1)]},
                initialDictsCache={'codebase=branch': [{'brid': 1}]}
        )
        self.builder_status.pendingBuildsCache.requestSubmitted(req=Mock())
        self.checkPendingBuildsCache(expectedCache={'': [Mock(brid=2)]})

    @defer.inlineCallbacks
    def test_requestCanceledResetsPendingBuildsCache(self):
        yield self.setupPendingBuildCache(
                initialCache={'codebase=branch': [Mock(brid=1)]},
                initialDictsCache={'codebase=branch': [{'brid': 1}]}
        )
        self.builder_status.pendingBuildsCache.requestCancelled(req=Mock())
        self.checkPendingBuildsCache(expectedCache={'': [Mock(brid=2)]})

    @defer.inlineCallbacks
    def test_buildStartedResetsPendingBuildsCache(self):
        yield self.setupPendingBuildCache(
                initialCache={'codebase=branch': [Mock(brid=1)]},
                initialDictsCache={'codebase=branch': [{'brid': 1}]}
        )
        self.builder_status.pendingBuildsCache.buildStarted(builderName='builder-01', state=Mock())
        self.checkPendingBuildsCache(expectedCache={'': [Mock(brid=2)]})

    @defer.inlineCallbacks
    def test_buildFinishedResetsPendingBuildsCache(self):
        yield self.setupPendingBuildCache(
                initialCache={'codebase=branch': [Mock(brid=1)]},
                initialDictsCache={'codebase=branch': [{'brid': 1}]}
        )
        self.builder_status.pendingBuildsCache.buildFinished(
                builderName='builder-01',
                state=Mock(),
                results=4,
        )
        self.checkPendingBuildsCache(expectedCache={'': [Mock(brid=2)]})

    @defer.inlineCallbacks
    def test_builderChangedStateDoesNotChangeCache(self):
        yield self.setupPendingBuildCache()

        self.builder_status.pendingBuildsCache.builderChangedState(
                builderName='builder-01',
                state=Mock(),
        )

        self.checkPendingBuildsCache()

    @defer.inlineCallbacks
    def test_getPendingBuilds(self):
        yield self.setupPendingBuildCache()
        cache = yield self.builder_status.pendingBuildsCache.getPendingBuilds()
        self.assertEquals(len(cache), 1)
        self.assertEquals(cache[0].brid, 2)

    def getBuildRequestInQueueMock(self, buildername, sourcestamps, sorted):
        expectedParam = [{'b_codebase': key, 'b_branch': value} for key, value in self.codebases.iteritems()]
        self.assertEquals(sourcestamps, expectedParam)

        def brdict(id):
            return {
                'brid': id,
                'buildsetid': id,
                'buildername': buildername,
                'priority': 50L, 'claimed': False,
                'claimed_at': None,
                'mine': False,
                'complete': False,
                'results': -1,
                'submitted_at': 1,
                'complete_at': None,
                'artifactbrid': None,
                'triggeredbybrid': None,
                'mergebrid': None,
                'startbrid': None,
                'slavepool': None,
            }

        return defer.succeed([brdict(id=1), brdict(id=2)])

    @defer.inlineCallbacks
    def test_getPendingBuildsByCodebases(self):
        yield self.setupPendingBuildCache()

        self.codebases = {'katana-buildbot': 'staging'}
        self.builder_status.master.db.buildrequests.getBuildRequestInQueue = self.getBuildRequestInQueueMock

        yield self.builder_status.pendingBuildsCache.getPendingBuilds(
                self.codebases
        )
        self.builder_status.master.db.buildrequests.getBuildRequestInQueue = defer.succeed([])
        cache = yield self.builder_status.pendingBuildsCache.getPendingBuilds(
                self.codebases
        )
        self.assertEquals(len(cache), 2)
        self.assertEquals(cache[0].brid, 1)

    @defer.inlineCallbacks
    def test_getTotal(self):
        yield self.setupPendingBuildCache()

        self.codebases = {'katana-buildbot': 'staging'}
        self.builder_status.master.db.buildrequests.getBuildRequestInQueue = self.getBuildRequestInQueueMock

        total = yield self.builder_status.pendingBuildsCache.getTotal(
                self.codebases
        )

        self.assertEquals(total, 2)

    @defer.inlineCallbacks
    def test_getPendingBuildsDictsByCodebases(self):
        yield self.setupPendingBuildCache()

        self.builder_status.master.db.buildrequests.getBuildRequestInQueue = self.getBuildRequestInQueueMock

        def asDict_async(self, codebases):
            return {
                'brid': self.brid,
            }

        self.patch(buildrequest.BuildRequestStatus, 'asDict_async', asDict_async)

        self.codebases = {'katana-buildbot': 'staging'}
        yield self.builder_status.pendingBuildsCache.getPendingBuildsDicts(
                self.codebases
        )

        self.builder_status.master.db.buildrequests.getBuildRequestInQueue = defer.succeed([])

        cache = yield self.builder_status.pendingBuildsCache.getPendingBuildsDicts(
                self.codebases
        )
        self.assertEquals(len(cache), 2)
        self.assertEquals(cache, [{'brid': 1}, {'brid': 2}])
