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
from twisted.internet import defer


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


class TestSingleProjectJsonResource(unittest.TestCase):

    @defer.inlineCallbacks
    def test_getBuildersByProject(self):

        katana = {'katana-buildbot':
                      {'project': 'general',
                       'display_name': 'Katana buildbot',
                       'defaultbranch': 'katana',
                       'repository': 'https://github.com/Unity-Technologies/buildbot.git',
                       'display_repository': 'https://github.com/Unity-Technologies/buildbot.git',
                       'branch': ['master', 'staging', 'katana']}}

        project = ProjectConfig(name="Katana", codebases=[katana])
        m = fakemaster.make_master(wantDb=True, testcase=self)
        m.getProject = lambda x: project
        m.botmaster.builderNames = ["builder-01", "builder-02", "builder-03", "builder-04"]
        master_status = master.Status(m)

        def mockBuilder(buildername, proj):
            builder = mock.Mock()
            builder.config = mock.Mock()
            builder.config.project = proj
            builder.builder_status = BuilderStatus(buildername, None, m)
            builder.builder_status.status = master_status
            builder.builder_status.project = proj
            builder.builder_status.pendingBuildCache = PendingBuildsCache(builder.builder_status)
            builder.builder_status.nextBuildNumber = 1
            builder.builder_status.basedir = '/basedir'
            builder.builder_status.saveYourself = lambda skipBuilds=True: True

            return builder

        m.botmaster.builders = {'builder-01': mockBuilder('builder-01', "project-01"),
                                'builder-02': mockBuilder('builder-02', "Katana"),
                                'builder-03': mockBuilder('builder-03', "Katana"), # has build on staging
                                'builder-04': mockBuilder('builder-04', "Katana"),
                                'builder-01': mockBuilder('builder-05', "project-02")}

        project_json = status_json.SingleProjectJsonResource(master_status, project)

        self.assertEqual(project_json.children.keys(), ['builder-02', 'builder-03', 'builder-04'])

        request = mock.Mock()
        request.args = {"katana-buildbot_branch": ["katana"]}
        request.getHeader = mock.Mock(return_value=None)
        request.prepath = ['json', 'projects', 'Katana']
        request.path = 'json/projects/Katana'

        project_dict = yield project_json.asDict(request)

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
                                     jsonBuilders('builder-04')], 'latestRevisions': {}}

        self.assertEqual(project_dict , expected_project_dict)
