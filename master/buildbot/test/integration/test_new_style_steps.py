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

from buildbot.process import buildstep
from buildbot.status import results
from buildbot.status.web import logs
from buildbot.test.fake.web import FakeRequest
from buildbot.test.util import steps
from twisted.internet import defer
from twisted.trial import unittest


class NewStyleStep(buildstep.BuildStep):

    @defer.inlineCallbacks
    def run(self):
        stdio = yield self.addLog('stdio')
        yield stdio.addStdout(u'Some stdout content\n')
        defer.returnValue(results.SUCCESS)


class TestNewStyleSteps(steps.BuildStepIntegrationMixin, unittest.TestCase):

    # New-style steps in eight have had a rocky start, as they are littered
    # with assertions about old methods, but those methods are still used
    # elsewhere in Buildbot.  These tests try to replicate the conditions in an
    # integrated fashion to flush out any similar errors."

    def setUp(self):
        return self.setUpBuildStepIntegration()

    def tearDown(self):
        return self.tearDownBuildStepIntegration()

    @defer.inlineCallbacks
    def test_render_new_style_logs(self):  # bug 2930
        self.setupStep(NewStyleStep())
        bs = yield self.runStep()

        # now try to render it in the WebStatus
        log_rsrc = logs.TextLog(bs.getSteps()[0].getLogs()[0])
        request = FakeRequest()
        yield request.test_render(log_rsrc)

    @defer.inlineCallbacks
    def test_check_logs_new_style(self):  # bug 2934
        self.setupStep(NewStyleStep())
        bs = yield self.runStep()

        # now ask the build status to check its logs
        bs.checkLogfiles()
