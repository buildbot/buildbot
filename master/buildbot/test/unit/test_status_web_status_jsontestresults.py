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
from buildbot.status.build import BuildStatus
from buildbot.status.builder import BuilderStatus
from buildbot.status.buildstep import BuildStepStatus
from buildbot.status.logfile import HTMLLogFile

import json
import mock
from buildbot.status.web.jsontestresults import JSONTestResource
from buildbot.test.fake.web import FakeRequest
from twisted.trial import unittest


class TestJSONTestResource(unittest.TestCase):
    def setupStatus(self):
        st = self.build_step_status = mock.Mock(BuildStepStatus)

        build_status = mock.Mock(BuildStatus)
        build_status.getNumber = lambda: 1
        builder_status = mock.Mock(BuilderStatus)
        builder_status.getFriendlyName = lambda: "BuilderStatusFriendlyName"
        builder_status.getName = lambda: "BuilderStatusName"

        builder_status.getProject = lambda: "Example Project"
        build_status.getBuilder = lambda: builder_status
        st.getBuild = lambda: build_status

        self.results = {
                0: 'Inconclusive',
                2: 'Skipped',
                3: 'Ignored',
                4: 'Success',
                5: 'Failure',
                6: 'Error',
                7: 'Cancelled'
            }

        return st

    def getLog(self, text, dumps=True):
        log = mock.Mock(HTMLLogFile)
        log.getName = "Tests"
        log.hasContent = True
        log.content_type = "json"
        log.getText = lambda: json.dumps(text) if dumps else text
        return log

    def getRequest(self):
        req = FakeRequest()
        req.method = "GET"
        req.uri = "/projects/Example%20Project/builders/runtests/builds/39/steps/Test%20IL2Cpp%20Unit%20Tests/logs/TestReport.html?_branch="
        req.clientproto = "HTTP/1.1"
        req.args = {}
        req.prepath = ""

        return req

    def test_log_resource_json_is_None(self):
        st = self.setupStatus()
        log = self.getLog(None)
        req = self.getRequest()
        json_resource = JSONTestResource(log, st)
        ctx = {}
        json_resource.content(req, ctx)

        self.assertFalse(hasattr(ctx, 'data'))
        self.assertEqual(ctx['builder_name'], 'BuilderStatusFriendlyName')
        self.assertEqual(ctx['path_to_builder'], 'projects/Example%20Project/builders/BuilderStatusName')
        self.assertEqual(ctx['path_to_builders'], 'projects/Example%20Project/builders')
        self.assertEqual(ctx['path_to_codebases'], 'projects/Example%20Project')
        self.assertEqual(ctx['path_to_build'], 'projects/Example%20Project/builders/BuilderStatusName/builds/1')
        self.assertEqual(ctx['build_number'], 1)
        self.assertEqual(ctx['selectedproject'], 'Example Project')
        self.assertFalse(hasattr(ctx, 'results'))

    def test_log_resource_not_json_format(self):
        st = self.setupStatus()
        log = self.getLog("{{", dumps=False)
        req = self.getRequest()
        json_resource = JSONTestResource(log, st)
        ctx = {}
        json_resource.content(req, ctx)

        self.assertTrue('data' not in ctx)
        self.assertTrue('results' not in ctx)
        self.assertEqual(ctx['builder_name'], 'BuilderStatusFriendlyName')
        self.assertEqual(ctx['path_to_builder'], 'projects/Example%20Project/builders/BuilderStatusName')
        self.assertEqual(ctx['path_to_builders'], 'projects/Example%20Project/builders')
        self.assertEqual(ctx['path_to_codebases'], 'projects/Example%20Project')
        self.assertEqual(ctx['path_to_build'], 'projects/Example%20Project/builders/BuilderStatusName/builds/1')
        self.assertEqual(ctx['build_number'], 1)
        self.assertEqual(ctx['selectedproject'], 'Example Project')

    def test_log_resource_correct_json(self):
        st = self.setupStatus()
        data = {'summary': {'testsCount': 123, 'successCount': 20}}
        log = self.getLog(data)
        req = self.getRequest()
        json_resource = JSONTestResource(log, st)
        ctx = {}
        json_resource.content(req, ctx)

        self.assertTrue(ctx['data'], data)

        self.assertEqual(ctx['builder_name'], 'BuilderStatusFriendlyName')
        self.assertEqual(ctx['path_to_builder'], 'projects/Example%20Project/builders/BuilderStatusName')
        self.assertEqual(ctx['path_to_builders'], 'projects/Example%20Project/builders')
        self.assertEqual(ctx['path_to_codebases'], 'projects/Example%20Project')
        self.assertEqual(ctx['path_to_build'], 'projects/Example%20Project/builders/BuilderStatusName/builds/1')
        self.assertEqual(ctx['build_number'], 1)
        self.assertEqual(ctx['selectedproject'], 'Example Project')
        self.assertEqual(ctx['results'], self.results)

    def test_log_resource_correct_json_incorrect_properties(self):
        st = self.setupStatus()
        data = {'summary': {'count': 123, 'success': 20}}
        log = self.getLog(data)
        req = self.getRequest()
        json_resource = JSONTestResource(log, st)
        ctx = {}
        json_resource.content(req, ctx)

        self.assertTrue(ctx['data'], data)

        self.assertEqual(ctx['builder_name'], 'BuilderStatusFriendlyName')
        self.assertEqual(ctx['path_to_builder'], 'projects/Example%20Project/builders/BuilderStatusName')
        self.assertEqual(ctx['path_to_builders'], 'projects/Example%20Project/builders')
        self.assertEqual(ctx['path_to_codebases'], 'projects/Example%20Project')
        self.assertEqual(ctx['path_to_build'], 'projects/Example%20Project/builders/BuilderStatusName/builds/1')
        self.assertEqual(ctx['build_number'], 1)
        self.assertEqual(ctx['selectedproject'], 'Example Project')



