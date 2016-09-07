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

import mock
from buildbot.status.web import status_json
from twisted.trial import unittest
from buildbot.config import ProjectConfig
from buildbot.status import master
from buildbot.test.fake import fakemaster, fakedb
from buildbot.status.builder import BuilderStatus, PendingBuildsCache
from buildbot.status.build import BuildStatus
from buildbot.status.slave import SlaveStatus
from twisted.internet import defer
from buildbot.status.results import SUCCESS
from buildbot.config import BuilderConfig
from buildbot.process.factory import BuildFactory
from buildbot.status.buildrequest import BuildRequestStatus
from buildbot.sourcestamp import SourceStamp
from buildbot.process.properties import Properties

class PastBuildsJsonResource(unittest.TestCase):
    def setUp(self):
        # set-up mocked request object
        self.request = mock.Mock()
        self.request.args = {}
        self.request.getHeader = mock.Mock(return_value=None)

        # set-up mocked builder_status object
        build = mock.Mock()
        build.asDict = mock.Mock(return_value="dummy")

        self.builder_status = mock.Mock()
        self.builder_status.generateFinishedBuildsAsync = \
            lambda branches=[], codebases={}, num_builds=None, results=None: defer.succeed([build])

        # set-up the resource object that will be used
        # by the tests with our mocked objects
        self.resource = \
            status_json.PastBuildsJsonResource(
                None, 1, builder_status=self.builder_status)

    @defer.inlineCallbacks
    def test_no_args_request(self):
        result = yield self.resource.asDict(self.request)
        self.assertEqual(result,
                         ["dummy"])

    @defer.inlineCallbacks
    def test_resources_arg_request(self):
        # test making a request with results=3 filter argument
        self.request.args = {"results": ["3"]}
        result = yield self.resource.asDict(self.request)
        self.assertEqual(result,
                         ["dummy"])

def setUpProject():
    katana = {'katana-buildbot':
                  {'project': 'general',
                   'display_name': 'Katana buildbot',
                   'defaultbranch': 'katana',
                   'repository': 'https://github.com/Unity-Technologies/buildbot.git',
                   'display_repository': 'https://github.com/Unity-Technologies/buildbot.git',
                   'branch': ['master', 'staging', 'katana']}}
    project = ProjectConfig(name="Katana", codebases=[katana])
    return project


def mockBuilder(master, master_status, buildername, proj):
    builder = mock.Mock()
    builder.config = BuilderConfig(name=buildername, friendly_name=buildername,
                                   project=proj,
                                   slavenames=['build-slave-01'],
                                   factory=BuildFactory(), description="Describing my builder",
                                   slavebuilddir="test", tags=['tag1', 'tag2'])
    builder.builder_status = BuilderStatus(buildername, None, master, description="Describing my builder")
    builder.builder_status.setSlavenames(['build-slave-01'])
    builder.builder_status.setTags(['tag1', 'tag2'])
    builder.builder_status.status = master_status
    builder.builder_status.project = proj
    builder.builder_status.pendingBuildsCache = PendingBuildsCache(builder.builder_status)
    builder.builder_status.nextBuildNumber = 1
    builder.builder_status.basedir = '/basedir'
    builder.builder_status.saveYourself = lambda skipBuilds=True: True

    return builder


def setUpFakeMasterWithProjects(project, obj):
    master = fakemaster.make_master(wantDb=True, testcase=obj)
    master.getProject = lambda x: project
    master.getProjects = lambda: {'Katana': project}
    return master


def setUpFakeMasterStatus(fakemaster):
    master_status = master.Status(fakemaster)
    slave = mock.Mock()
    slave.getFriendlyName = lambda: 'build-slave-01'
    master_status.getSlave = lambda x: slave
    return master_status


def fakeBuildStatus(master, builder, num):
    build_status = BuildStatus(builder.builder_status, master, num)
    build_status.started = 1422441500
    build_status.finished = 1422441501.21
    build_status.reason = 'A build was forced by user@localhost'
    build_status.slavename = 'build-slave-01'
    build_status.results = SUCCESS
    return build_status


class TestBuildJsonResource(unittest.TestCase):
    def setUp(self):
        self.project = setUpProject()

        self.master = setUpFakeMasterWithProjects(self.project, self)

        self.master_status = setUpFakeMasterStatus(self.master)
        self.master.status = self.master_status

        self.request = mock.Mock()
        self.request.args = {"katana-buildbot_branch": ["katana"]}
        self.request.getHeader = mock.Mock(return_value=None)
        self.request.prepath = ['json', 'projects', 'Katana']
        self.request.path = 'json/projects/Katana'


    @defer.inlineCallbacks
    def test_getBuildJsonResource(self):
        builder = mockBuilder(self.master, self.master_status, "builder-01", "Katana")
        build_status = fakeBuildStatus(self.master, builder, 1)
        ss = SourceStamp(branch='b', sourcestampsetid=1, repository='https://github.com/test/repo',
                         revision="abcdef123456789")
        build_status.getSourceStamps = lambda: [ss]
        build_json = status_json.BuildJsonResource(self.master_status, build_status)
        build_dict = yield build_json.asDict(self.request)

        self.assertEqual(build_dict,
                         {'results_text': 'success', 'slave': 'build-slave-01',
                          'slave_url': None, 'builderName': 'builder-01',
                          'builder_tags': ['tag1', 'tag2'],
                          'url':
                              {'path': 'http://localhost:8080/builders/builder-01/builds/1' +
                                       '?katana-buildbot_branch=katana&_branch=b', 'text': 'builder-01 #1'},
                          'text': [], 'sourceStamps': [{'codebase': '', 'revision_short': 'abcdef123456',
                                                        'totalChanges': 0,
                                                        'repository': 'https://github.com/test/repo', 'hasPatch': False,
                                                        'project': '',
                                                        'branch': 'b',
                                                        'display_repository': 'https://github.com/test/repo',
                                                        'changes': [],
                                                        'revision': 'abcdef123456789',
                                                        'url': u'https://github.com/test/repo/commit/abcdef123456789'}],
                          'results': 0, 'number': 1, 'currentStep': None,
                          'times': (1422441500, 1422441501.21),
                          'buildChainID': None,
                          'brids': [],
                          'owners': None, 'submittedTime': None,
                          'blame': [],
                          'builder_url': 'http://localhost:8080/projects/Katana/builders/builder-01' +
                                         '?katana-buildbot_branch=katana&_branch=b',
                          'reason': 'A build was forced by user@localhost', 'eta': None,
                          'isWaiting': False, 'builderFriendlyName': 'builder-01',
                          'steps': [], 'properties': [], 'slave_friendly_name': 'build-slave-01', 'logs': []})


class TestBuilderSlavesJsonResources(unittest.TestCase):
    def setUp(self):
        self.project = setUpProject()

        self.master = setUpFakeMasterWithProjects(self.project, self)

        self.master_status = setUpFakeMasterStatus(self.master)
        self.master.status = self.master_status

        self.request = mock.Mock()
        self.request.args = {"katana-buildbot_branch": ["katana"]}
        self.request.getHeader = mock.Mock(return_value=None)
        self.request.prepath = ['json', 'projects', 'Katana']
        self.request.path = 'json/projects/Katana'

    @defer.inlineCallbacks
    def test_getBuilderSlavesJsonResources(self):
        builder = mockBuilder(self.master, self.master_status, "builder-01", "Katana")

        self.master_status.getBuilderNames = lambda: ["builder-01"]
        self.master_status.getBuilder = lambda x: builder.builder_status

        def getSlaveStatus(slave):
            slave_status = SlaveStatus(slave)
            slave_status.master = self.master
            return slave_status

        self.master_status.getSlave = getSlaveStatus

        slaves = status_json.BuilderSlavesJsonResources(self.master_status, builder.builder_status)
        slaves_dict = yield slaves.asDict(self.request)

        self.assertEqual(slaves_dict,
                         {'build-slave-01': {
                             'name': 'build-slave-01',
                             'url': 'http://localhost:8080/buildslaves/build-slave-01',
                             'runningBuilds': [], 'friendly_name': None, 'admin': None, 'host': None,
                             'version': None, 'connected': False, 'eid': -1, 'lastMessage': 0,
                             'health': 0,
                             'fqdn': None,
                             'slaveManagerUrl': None,
                             'paused': False,
                             'graceful_shutdown': False,
                             'builders': [
                                 {'url': 'http://localhost:8080/projects/Katana/builders/builder-01',
                                  'project': 'Katana',
                                  'friendly_name': 'builder-01', 'name': 'builder-01'}],
                             'access_uri': None}})


class TestPastBuildsJsonResource(unittest.TestCase):
    def setUp(self):
        self.project = setUpProject()

        self.master = setUpFakeMasterWithProjects(self.project, self)

        self.master_status = setUpFakeMasterStatus(self.master)
        self.master.status = self.master_status

        self.request = mock.Mock()
        self.request.args = {"katana-buildbot_branch": ["katana"]}
        self.request.getHeader = mock.Mock(return_value=None)
        self.request.prepath = ['json', 'projects', 'Katana']
        self.request.path = 'json/projects/Katana'

    @defer.inlineCallbacks
    def test_getPastBuildsJsonResource(self):
        builder = mockBuilder(self.master, self.master_status, "builder-01", "Katana")

        def mockFinishedBuilds(branches=[], codebases={},
                               num_builds=None,
                               max_buildnum=None,
                               finished_before=None,
                               results=None,
                               max_search=2000,
                               useCache=False):


            finished_builds = []
            for n in range(15):
                finished_builds.append(fakeBuildStatus(self.master, builder, n))
            return defer.succeed(finished_builds)

        builder.builder_status.generateFinishedBuildsAsync = mockFinishedBuilds

        builds_json = status_json.PastBuildsJsonResource(self.master_status, 15, builder_status=builder.builder_status)
        builds_dict = yield builds_json.asDict(self.request)
        self.assertTrue(len(builds_dict) == 15)

        def expectedDict(num):
            return {'artifacts': None, 'blame': [], 'builderFriendlyName': 'builder-01', 'builderName': 'builder-01', 'builder_tags': ['tag1', 'tag2'],
                    'builder_url': 'http://localhost:8080/projects/Katana/builders/builder-01?katana-buildbot_branch=katana',
                    'currentStep': None, 'eta': None, 'failure_url': None, 'isWaiting': False, 'logs': [],
                    'number': num, 'properties': [], 'reason': 'A build was forced by user@localhost',
                    'results': 0, 'results_text': 'success', 'slave': 'build-slave-01',
                    'slave_friendly_name': 'build-slave-01', 'slave_url': None,
                    'sourceStamps': [], 'steps': [], 'buildChainID': None,
                    'brids': [],
                    'owners': None,
                     'submittedTime': None,
                    'text': [], 'times': (1422441500, 1422441501.21),
                    'url': {
                        'path':
                            'http://localhost:8080/builders/builder-01/builds/%d?katana-buildbot_branch=katana' % num,
                        'text': 'builder-01 #%d' % num}}

        for b in builds_dict:
            self.assertEqual(b, expectedDict(builds_dict.index(b)))


class TestSingleProjectJsonResource(unittest.TestCase):
    def setUp(self):
        self.project = setUpProject()

        self.master = setUpFakeMasterWithProjects(self.project, self)

        self.master_status = setUpFakeMasterStatus(self.master)
        self.master.status = self.master_status

        self.request = mock.Mock()
        self.request.args = {"katana-buildbot_branch": ["katana"]}
        self.request.getHeader = mock.Mock(return_value=None)
        self.request.prepath = ['json', 'projects', 'Katana']
        self.request.path = 'json/projects/Katana'

    @defer.inlineCallbacks
    def setupProject(self, builders):
        self.master.botmaster.builderNames = builders.keys()

        for bn, project in builders.items():
            self.master.botmaster.builders[bn] = mockBuilder(self.master, self.master_status, bn, project)

        row = [
            fakedb.BuildRequest(id=1, buildsetid=1, buildername='builder-02', priority=20, submitted_at=1450171024),
            fakedb.SourceStampSet(id=1),
            fakedb.Buildset(id=1, sourcestampsetid=1),
            fakedb.SourceStamp(id=1, revision='az', codebase='cb', sourcestampsetid=1, branch='master', repository='z')
        ]
        yield self.master.db.insertTestData(row)

    def jsonBuilders(self, builder_name, pendingBuilds=0, pendingBuildRequests=None):
        json = {
            'name': builder_name,
            'tags': ['tag1', 'tag2'],
            'url': 'http://localhost:8080/projects/Katana/builders/' + builder_name +'?katana-buildbot_branch=katana',
            'friendly_name': builder_name, 'description': 'Describing my builder',
            'project': 'Katana',
            'state': 'offline',
            'slaves': ['build-slave-01'],
            'startSlavenames ': [],
            'currentBuilds': [],
            'pendingBuilds': pendingBuilds
        }

        if pendingBuildRequests is not None:
            json['pendingBuildRequests'] = pendingBuildRequests

        return json

    def expectedProjectDict(self, builders, latestRevisions={}):
        return {
            'comparisonURL': '../../projects/Katana/comparison?builders0=katana-buildbot%3Dkatana',
            'builders': builders,
            'latestRevisions': latestRevisions
        }

    @defer.inlineCallbacks
    def test_getBuildersByProject(self):
        builders = {
            'builder-01': 'project-01',
            "builder-02": 'Katana',
            "builder-03": 'Katana',
            "builder-04": 'Katana',
            "builder-05": 'project-02',
        }

        yield self.setupProject(builders=builders)

        project_json = status_json.SingleProjectJsonResource(self.master_status, self.project)

        latestRevisions = {'https://github.com/Unity-Technologies/buildbot.git': {
                'codebase': 'katana-buildbot',
                'display_repository': 'https://github.com/Unity-Technologies/buildbot.git',
                'branch': 'Katana', 'revision': u'0:835be7494fb4'}}

        def getObjectStateByKey(objects, filteredKey, storedKey):
            return latestRevisions

        project_json.status.master.db.state.getObjectStateByKey = getObjectStateByKey

        self.assertEqual(project_json.children.keys(), ['builder-02', 'builder-03', 'builder-04'])

        project_dict = yield project_json.asDict(self.request)

        expected_project_dict = self.expectedProjectDict(
                builders=[
                    self.jsonBuilders('builder-02', pendingBuilds=1),
                    self.jsonBuilders('builder-03'),
                    self.jsonBuilders('builder-04')
                ],
                latestRevisions=latestRevisions
        )

        self.assertEqual(project_dict, expected_project_dict)

    @defer.inlineCallbacks
    def test_getBuildersWithPendingBuildsByProject(self):
        yield self.setupProject(builders={'builder-02': 'Katana'})
        self.request.args['pending_builds'] = ['1']
        project_json = status_json.SingleProjectJsonResource(self.master_status, self.project)
        project_dict = yield project_json.asDict(self.request)

        def getSource(url=True):
            source = {
                'revision': 'az',
                'revision_short': 'az',
                'hasPatch': False,
                'branch': 'master',
                'changes': [],
                'project': 'proj',
                'repository': 'z',
                'codebase': 'cb',
                'totalChanges': 0
            }
            if url:
                source['url']= None
            return source

        pending = [
            {
                'brid': 1,
                'source': getSource(),
                'sources': [getSource(url=False)],
                'properties': [],
                'priority': 20,
                'builderName': 'builder-02',
                'reason': 'because',
                'slaves': ['build-slave-01'],
                'submittedAt': 1450171024,
                'builderFriendlyName': 'builder-02',
                'builderURL': 'http://localhost:8080/projects/Katana/builders/builder-02?katana-buildbot_branch=katana',
                'results': -1,
                'builds': [],
                'lastBuildNumber': None
            }
        ]

        expected_project = self.expectedProjectDict(
                builders=[self.jsonBuilders('builder-02', pendingBuilds=len(pending), pendingBuildRequests=pending)]
        )

        self.assertEquals(project_dict, expected_project)

    @defer.inlineCallbacks
    def test_getBuildersByProjectWithLatestBuilds(self):
        self.master.botmaster.builderNames = ["builder-01"]

        builder = mockBuilder(self.master, self.master_status, "builder-01", "Katana")
        self.master.botmaster.builders = {'builder-01': builder}

        def mockFinishedBuildsAsync(branches=[], codebases={},
                               num_builds=None,
                               max_buildnum=None,
                               finished_before=None,
                               results=None,
                               max_search=2000,
                               useCache=False):
            return defer.succeed([fakeBuildStatus(self.master, builder, 1)])

        builder.builder_status.generateFinishedBuildsAsync = mockFinishedBuildsAsync

        project_json = status_json.SingleProjectJsonResource(self.master_status, self.project)

        self.assertEqual(project_json.children.keys(), ['builder-01'])

        project_dict = yield project_json.asDict(self.request)

        expected_project_dict = \
            {'comparisonURL': '../../projects/Katana/comparison?builders0=katana-buildbot%3Dkatana',
             'builders':
                 [{'latestBuild': {
                     'results_text': 'success',
                     'slave': 'build-slave-01',
                     'slave_url': None,
                     'builderName': 'builder-01',
                     'builder_tags': ['tag1', 'tag2'],
                     'url':
                         {'path':
                              'http://localhost:8080/projects/Katana/builders/builder-01' +
                              '/builds/1?katana-buildbot_branch=katana',
                          'text': 'builder-01 #1'},
                     'text': [],
                     'sourceStamps': [],
                     'results': 0,
                     'number': 1, 'artifacts': None, 'blame': [], 'buildChainID': None,
                     'brids': [],
                     'owners': None,
                     'submittedTime': None,
                     'builder_url': 'http://localhost:8080/projects/Katana/builders/builder-01' +
                                    '?katana-buildbot_branch=katana',
                     'reason': 'A build was forced by user@localhost',
                     'eta': None, 'builderFriendlyName': 'builder-01',
                     'failure_url': None, 'slave_friendly_name': 'build-slave-01',
                     'times': (1422441500, 1422441501.21)},
                   'name': 'builder-01', 'tags': ['tag1', 'tag2'],
                   'url': 'http://localhost:8080/projects/Katana/builders/builder-01?katana-buildbot_branch=katana',
                   'description': 'Describing my builder',
                   'friendly_name': 'builder-01', 'startSlavenames ': [],
                   'project': 'Katana', 'state': 'offline', 'slaves': ['build-slave-01'],
                   'currentBuilds': [], 'pendingBuilds': 0}],
             'latestRevisions': {}}

        self.assertEqual(project_dict, expected_project_dict)


class TestSingleProjectBuilderJsonResource(unittest.TestCase):
    def setUp(self):
        self.project = setUpProject()

        self.master = setUpFakeMasterWithProjects(self.project, self)

        self.master_status = setUpFakeMasterStatus(self.master)
        self.master.status = self.master_status

        self.request = mock.Mock()
        self.request.args = {"katana-buildbot_branch": ["katana"]}
        self.request.getHeader = mock.Mock(return_value=None)
        self.request.prepath = ['json', 'projects', 'Katana']
        self.request.path = 'json/projects/Katana'

    @defer.inlineCallbacks
    def test_getSingleProjectBuilder(self):
        builder = mockBuilder(self.master, self.master_status, "builder-01", "Katana")

        project_builder_json = status_json.SingleProjectBuilderJsonResource(self.master_status, builder.builder_status)

        project_builder_dict = yield project_builder_json.asDict(self.request)

        self.assertEqual(project_builder_dict,
                         {'name': 'builder-01',
                          'tags': ['tag1', 'tag2'],
                          'url': 'http://localhost:8080/projects/Katana/builders/' +
                                 'builder-01?katana-buildbot_branch=katana',
                          'friendly_name': 'builder-01', 'description': 'Describing my builder',
                          'project': 'Katana', 'startSlavenames ': [],
                          'state': 'offline', 'slaves': ['build-slave-01'], 'currentBuilds': [], 'pendingBuilds': 0})

    @defer.inlineCallbacks
    def test_getSingleProjectBuilderWithLatestRev(self):
        builder = mockBuilder(self.master, self.master_status, "builder-01", "Katana")

        project_builder_json = status_json.SingleProjectBuilderJsonResource(self.master_status, builder.builder_status,
                                                                            True)

        project_builder_dict = yield project_builder_json.asDict(self.request)

        self.assertEqual(project_builder_dict,
                         {'name': 'builder-01',
                          'tags': ['tag1', 'tag2'],
                          'latestRevisions': {},
                          'url': 'http://localhost:8080/projects/Katana/builders/' +
                                 'builder-01?katana-buildbot_branch=katana',
                          'friendly_name': 'builder-01',
                          'description': 'Describing my builder', 'startSlavenames ': [],
                          'project': 'Katana',
                          'state': 'offline', 'slaves': ['build-slave-01'], 'currentBuilds': [], 'pendingBuilds': 0})


class TestSinglePendingBuildsJsonResource(unittest.TestCase):
    def setUp(self):
        self.project = setUpProject()

        self.master = setUpFakeMasterWithProjects(self.project, self)

        self.master_status = setUpFakeMasterStatus(self.master)
        self.master.status = self.master_status

        self.request = mock.Mock()
        self.request.args = {"katana-buildbot_branch": ["katana"]}
        self.request.getHeader = mock.Mock(return_value=None)
        self.request.prepath = ['json', 'projects', 'Katana']
        self.request.path = 'json/projects/Katana'


    @defer.inlineCallbacks
    def test_getSinglePendingBuilds(self):
        builder = mockBuilder(self.master, self.master_status, "builder-01", "Katana")

        self.master_status.getBuilder = lambda x: builder.builder_status

        def getBuildRequestStatus(id):
            brstatus = BuildRequestStatus(builder.builder_status.name, id, self.master_status)
            brstatus._buildrequest = mock.Mock()
            brstatus.getSubmitTime = lambda: 1418823086
            brstatus.getResults = lambda : -1
            brstatus.getReason = lambda: 'because'
            brstatus.getPriority = lambda : 50

            ss = SourceStamp(branch='b', sourcestampsetid=1, repository='z')
            brstatus.getSourceStamps = lambda: {}
            brstatus.getSourceStamp = lambda: ss
            brstatus.getBuildProperties = lambda: Properties()
            return brstatus

        def fetchPendingBuildRequestStatuses(codebases={}):
            requests = [1, 2, 3]
            return [getBuildRequestStatus(id) for id in requests]

        builder.builder_status.pendingBuildsCache.fetchPendingBuildRequestStatuses = fetchPendingBuildRequestStatuses

        pending_json = status_json.SinglePendingBuildsJsonResource(self.master_status, builder.builder_status)
        pending_dict = yield pending_json.asDict(self.request)

        def pendingBuildRequestDict(brid):
            return {'brid': brid, 'builderFriendlyName': 'builder-01', 'builderName': 'builder-01',
                    'builderURL': 'http://localhost:8080/projects/Katana/builders/builder-01' +
                                  '?katana-buildbot_branch=katana',
                    'builds': [],
                    'properties': [],
                    'lastBuildNumber': None,
                    'reason': 'because',
                    'slaves': ['build-slave-01'],
                    'source': {'branch': 'b',
                               'changes': [],
                               'codebase': '',
                               'hasPatch': False,
                               'totalChanges': 0,
                               'project': '',
                               'repository': 'z',
                               'revision': None,
                               'revision_short': '',
                               'url': ''},
                    'sources': [],
                    'submittedAt': 1418823086,
                    'results': -1,
                    'priority': 50}

        self.assertEqual(pending_dict, [pendingBuildRequestDict(1),
                                        pendingBuildRequestDict(2),
                                        pendingBuildRequestDict(3)])


class TestQueueJsonResource(unittest.TestCase):
    def setUp(self):
        self.project = setUpProject()

        self.master = setUpFakeMasterWithProjects(self.project, self)

        self.master_status = setUpFakeMasterStatus(self.master)
        self.master.status = self.master_status

        builder = mockBuilder(self.master, self.master_status, "bldr1", "Katana")

        def getBuilder(name):
            if name == "bldr1":
                return builder
            return None

        self.master_status.getBuilder = getBuilder

        self.request = mock.Mock()
        self.request.getHeader = mock.Mock(return_value=None)
        self.request.prepath = ['json', 'buildqueue']
        self.request.path = '/json/buildqueue'

    @defer.inlineCallbacks
    def test_getQueueJsonResource(self):
        testdata = [fakedb.BuildRequest(id=1, buildsetid=1, buildername="bldr1",priority=20, submitted_at=1449578391),
                    fakedb.BuildRequest(id=2, buildsetid=2, buildername="bldr2",priority=50, submitted_at=1450171039)]

        testdata += [fakedb.Buildset(id=idx, sourcestampsetid=idx) for idx in xrange(1, 3)]
        testdata += [fakedb.SourceStamp(sourcestampsetid=idx, branch='branch_%d' % idx) for idx in xrange(1, 3)]

        yield self.master.db.insertTestData(testdata)

        queue = status_json.QueueJsonResource(self.master_status)
        queue_json = yield queue.asDict(self.request)
        self.assertEquals((len(queue_json), queue_json[0]['brid']), (1, 1))


class TestAliveJsonResource(unittest.TestCase):
    def test_alive(self):
        '''
        Tests the alive check for online status.
        '''
        alive_json = status_json.AliveJsonResource(None)
        self.assertEqual(alive_json.asDict(None), 1)
