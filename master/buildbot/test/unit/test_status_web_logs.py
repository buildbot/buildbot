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
from buildbot.status.web.jsontestresults import JSONTestResource

from buildbot.status.buildstep import BuildStepStatus
from buildbot.status.logfile import HTMLLogFile
from buildbot.status.web.logs import LogsResource

import mock
from buildbot.status.web.xmltestresults import XMLTestResource
from twisted.trial import unittest
from twisted.web.resource import NoResource


class TestLogsResource(unittest.TestCase):
    def setupStatus(self, name=None, text=None, has_content=False, content_type=None):
        st = self.build_step_status = mock.Mock(BuildStepStatus)
        self.logs = []
        st.getLogs = lambda: self.logs

        if name is None:
            return st

        log = mock.Mock(HTMLLogFile)
        log.getName = lambda: name
        log.hasContent = lambda: has_content
        if content_type is not None:
            log.content_type = content_type
        log.getText = lambda: text
        self.logs.append(log)

        return st

    def test_log_resource_json(self):
        st = self.setupStatus("test", "", True, "json")
        logs_resource = LogsResource(st)
        res = logs_resource.getChild("test", "")

        self.assertIsInstance(res, JSONTestResource)

    def test_log_resource_xml(self):
        logs_resource = LogsResource(self.setupStatus("test", "", True, "xml"))
        res = logs_resource.getChild("test", "")

        self.assertIsInstance(res, XMLTestResource)

    def test_log_resource_xml_no_content_type(self):
        logs_resource = LogsResource(self.setupStatus("test", "nosetests", True))
        res = logs_resource.getChild("test", "")

        self.assertIsInstance(res, XMLTestResource)

    def test_log_resource_xml_content(self):
        logs_resource = LogsResource(self.setupStatus("test", "<..><xml-stylesheet..!", True))
        res = logs_resource.getChild("test", "")

        self.assertIsInstance(res, XMLTestResource)

    def test_log_resource_xml_notests_in_content(self):
        logs_resource = LogsResource(self.setupStatus("test", "dfsd _nosetests", True))
        res = logs_resource.getChild("test", "")

        self.assertIsInstance(res, XMLTestResource)

    def test_log_resource_default(self):
        logs_resource = LogsResource(self.setupStatus("test", "", True))
        res = logs_resource.getChild("test", "")

        self.assertIsInstance(res, HTMLLogFile)

    def test_log_resource_no_log(self):
        logs_resource = LogsResource(self.setupStatus("test", "", True))
        res = logs_resource.getChild("test1", "")

        self.assertIsInstance(res, NoResource)

    def test_log_resource_no_logs(self):
        logs_resource = LogsResource(self.setupStatus())
        res = logs_resource.getChild("test1", "")

        self.assertIsInstance(res, NoResource)
