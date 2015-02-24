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
from buildbot.test.fake import fakemaster
from buildbot.status.builder import BuilderStatus, PendingBuildsCache
from buildbot.status.build import BuildStatus
from twisted.internet import defer
from buildbot.status.results import SUCCESS
from buildbot.config import BuilderConfig
from buildbot.process.factory import BuildFactory


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
        self.builder_status.generateFinishedBuilds = \
            mock.Mock(return_value=[build])

        # set-up the resource object that will be used
        # by the tests with our mocked objects
        self.resource = \
            status_json.PastBuildsJsonResource(
                None, 1, builder_status=self.builder_status)

    def test_no_args_request(self):

        self.assertEqual(self.resource.asDict(self.request),
                         ["dummy"])

        self.builder_status.generateFinishedBuilds.assert_called_once_with(
            codebases={},
            branches=[],
            num_builds=1,
            results=None
        )

    def test_resources_arg_request(self):
        # test making a request with results=3 filter argument
        self.request.args = {"results": ["3"]}
        self.assertEqual(self.resource.asDict(self.request),
                         ["dummy"])

        self.builder_status.generateFinishedBuilds.assert_called_once_with(
            codebases={},
            branches=[],
            num_builds=1,
            results=[3]
        )


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
                  factory=BuildFactory(),
                  slavebuilddir="test", tags=['tag1', 'tag2'])
    builder.builder_status = BuilderStatus(buildername, None, master)
    builder.builder_status.status = master_status
    builder.builder_status.project = proj
    builder.builder_status.pendingBuildCache = PendingBuildsCache(builder.builder_status)
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
    def test_getBuildersByProject(self):

        self.master.botmaster.builderNames = ["builder-01", "builder-02", "builder-03", "builder-04"]

        self.master.botmaster.builders = {'builder-01': mockBuilder(self.master, self.master_status,
                                                                    'builder-01', "project-01"),
                                'builder-02': mockBuilder(self.master, self.master_status,
                                                          'builder-02', "Katana"),
                                'builder-03': mockBuilder(self.master, self.master_status,
                                                          'builder-03', "Katana"),
                                'builder-04': mockBuilder(self.master, self.master_status,
                                                          'builder-04', "Katana"),
                                'builder-01': mockBuilder(self.master, self.master_status,
                                                          'builder-05', "project-02")}

        project_json = status_json.SingleProjectJsonResource(self.master_status, self.project)

        def getObjectStateByKey(objects, filteredKey, storedKey):
            lastrev = {'https://github.com/Unity-Technologies/buildbot.git':
                           {'codebase': 'katana-buildbot',
                            'display_repository': 'https://github.com/Unity-Technologies/buildbot.git',
                            'branch': 'Katana', 'revision': u'0:835be7494fb4'}}
            return lastrev

        project_json.status.master.db.state.getObjectStateByKey = getObjectStateByKey

        self.assertEqual(project_json.children.keys(), ['builder-02', 'builder-03', 'builder-04'])

        project_dict = yield project_json.asDict(self.request)

        def jsonBuilders(builder_name):
            return {'name': builder_name, 'tags': [],
                'url': 'http://localhost:8080/projects/Katana/builders/' + builder_name +
                       '?katana-buildbot_branch=katana',
                'friendly_name': builder_name,
                'project': 'Katana',
                'state': 'offline',
                'slaves': [], 'currentBuilds': [], 'pendingBuilds': 0}

        expected_project_dict = {'comparisonURL': '../../projects/Katana/comparison?builders0=katana-buildbot%3Dkatana',
                                 'builders': [
                                     jsonBuilders('builder-02'),
                                     jsonBuilders('builder-03'),
                                     jsonBuilders('builder-04')],
                                 'latestRevisions':
                                     {'https://github.com/Unity-Technologies/buildbot.git':
                                          {'branch': 'Katana',
                                           'codebase': 'katana-buildbot',
                                           'display_repository': 'https://github.com/Unity-Technologies/buildbot.git',
                                           'revision': u'835be7494fb4'}}}

        self.assertEqual(project_dict , expected_project_dict)


    @defer.inlineCallbacks
    def test_getBuildersByProjectWithLatestBuilds(self):

        self.master.botmaster.builderNames = ["builder-01"]

        builder = mockBuilder(self.master, self.master_status, "builder-01", "Katana")
        self.master.botmaster.builders = {'builder-01': builder}

        def mockFinishedBuilds(branches=[], codebases={},
                               num_builds=None,
                               max_buildnum=None,
                               finished_before=None,
                               results=None,
                               max_search=2000,
                               useCache=False):

            build_status = BuildStatus(builder.builder_status, self.master, 1)
            build_status.finished = 1422441501.21
            build_status.reason ='A build was forced by user@localhost'
            build_status.slavename = 'build-slave-01'
            build_status.results = SUCCESS

            return [build_status]

        builder.builder_status.generateFinishedBuilds = mockFinishedBuilds

        project_json = status_json.SingleProjectJsonResource(self.master_status, self.project)

        self.assertEqual(project_json.children.keys(), ['builder-01'])

        project_dict = yield project_json.asDict(self.request)

        expected_project_dict = \
            {'comparisonURL': '../../projects/Katana/comparison?builders0=katana-buildbot%3Dkatana',
             'builders':
                 [{'latestBuild':
                       {'results_text': 'success',
                        'slave': 'build-slave-01',
                        'slave_url': None,
                        'builderName': 'builder-01',
                        'url':
                            {'path':
                                 'http://localhost:8080/projects/Katana/builders/builder-01'+
                                 '/builds/1?katana-buildbot_branch=katana',
                             'text': 'builder-01 #1'},
                        'text': [],
                        'sourceStamps': [],
                        'results': 0,
                        'number': 1, 'artifacts': None, 'blame': [],
                        'builder_url': 'http://localhost:8080/projects/Katana/builders/builder-01'+
                                       '?katana-buildbot_branch=katana',
                        'reason': 'A build was forced by user@localhost',
                        'eta': None, 'builderFriendlyName': 'builder-01',
                        'failure_url': None, 'slave_friendly_name': 'build-slave-01',
                        'times': (None, 1422441501.21, 1422441501.21)},
                   'name': 'builder-01', 'tags': [],
                   'url': 'http://localhost:8080/projects/Katana/builders/builder-01?katana-buildbot_branch=katana',
                   'friendly_name': 'builder-01',
                   'project': 'Katana', 'state': 'offline', 'slaves': [], 'currentBuilds': [], 'pendingBuilds': 0}],
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
                          'tags': [],
                          'url': 'http://localhost:8080/projects/Katana/builders/'+
                                 'builder-01?katana-buildbot_branch=katana',
                          'friendly_name': 'builder-01',
                          'project': 'Katana',
                          'state': 'offline', 'slaves': [], 'currentBuilds': [], 'pendingBuilds': 0})
