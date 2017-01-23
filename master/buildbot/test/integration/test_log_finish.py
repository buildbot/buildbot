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

from __future__ import absolute_import
from __future__ import print_function

from twisted.internet import defer

from buildbot.plugins import steps
from buildbot.process.results import EXCEPTION
from buildbot.process.results import SUCCESS
from buildbot.test.util.integration import RunMasterBase


class TestLog(RunMasterBase):
    # master configuration

    def masterConfig(self, step):
        c = {}
        from buildbot.config import BuilderConfig
        from buildbot.process.factory import BuildFactory
        from buildbot.plugins import schedulers

        c['schedulers'] = [
            schedulers.AnyBranchScheduler(
                name="sched",
                builderNames=["testy"])]

        f = BuildFactory()
        f.addStep(step)
        c['builders'] = [
            BuilderConfig(name="testy",
                          workernames=["local1"],
                          factory=f)]
        return c

    @defer.inlineCallbacks
    def test_shellcommand(self):

        class MyStep(steps.ShellCommand):

            def _newLog(obj, name, type, logid, logEncoding):
                r = steps.ShellCommand._newLog(obj, name, type, logid, logEncoding)
                self.curr_log = r
                return self.curr_log

        step = MyStep(command='echo hello')

        yield self.setupConfig(self.masterConfig(step))

        change = dict(branch="master",
                      files=["foo.c"],
                      author="me@foo.com",
                      comments="good stuff",
                      revision="HEAD",
                      project="none")
        build = yield self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        self.assertEqual(build['results'], SUCCESS)
        self.assertTrue(self.curr_log.finished)

    @defer.inlineCallbacks
    def test_mastershellcommand(self):

        class MyStep(steps.MasterShellCommand):

            def _newLog(obj, name, type, logid, logEncoding):
                r = steps.MasterShellCommand._newLog(obj, name, type, logid, logEncoding)
                self.curr_log = r
                return self.curr_log

        step = MyStep(command='echo hello')

        yield self.setupConfig(self.masterConfig(step))

        change = dict(branch="master",
                      files=["foo.c"],
                      author="me@foo.com",
                      comments="good stuff",
                      revision="HEAD",
                      project="none")
        build = yield self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        self.assertEqual(build['results'], SUCCESS)
        self.assertTrue(self.curr_log.finished)

    @defer.inlineCallbacks
    def test_mastershellcommand_issue(self):

        class MyStep(steps.MasterShellCommand):

            def _newLog(obj, name, type, logid, logEncoding):
                r = steps.MasterShellCommand._newLog(obj, name, type, logid, logEncoding)
                self.curr_log = r
                self.patch(r, "finish", lambda: defer.fail(RuntimeError('Could not finish')))
                return self.curr_log

        step = MyStep(command='echo hello')

        yield self.setupConfig(self.masterConfig(step))

        change = dict(branch="master",
                      files=["foo.c"],
                      author="me@foo.com",
                      comments="good stuff",
                      revision="HEAD",
                      project="none")
        build = yield self.doForceBuild(wantSteps=True, useChange=change, wantLogs=True)
        self.assertEqual(build['buildid'], 1)
        self.assertFalse(self.curr_log.finished)
        self.assertEqual(build['results'], EXCEPTION)
        errors = self.flushLoggedErrors()
        self.assertEqual(len(errors), 1)
        error = errors[0]
        self.assertEqual(error.getErrorMessage(), 'Could not finish')
