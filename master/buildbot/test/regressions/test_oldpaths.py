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

from twisted.trial import unittest


def deprecatedImport(fn):
    def wrapper(self):
        fn(self)
        warnings = self.flushWarnings()
        # on older Pythons, this warning appears twice, so use collapse it
        if len(warnings) == 2 and warnings[0] == warnings[1]:
            del warnings[1]
        self.assertEqual(len(warnings), 1, "got: %r" % (warnings,))
        self.assertEqual(warnings[0]['category'], DeprecationWarning)
    return wrapper


class OldImportPaths(unittest.TestCase):

    """
    Test that old, deprecated import paths still work.
    """

    def test_scheduler_Scheduler(self):
        from buildbot.scheduler import Scheduler
        assert Scheduler

    def test_schedulers_basic_Scheduler(self):
        # renamed to basic.SingleBranchScheduler
        from buildbot.schedulers.basic import Scheduler
        assert Scheduler

    def test_scheduler_AnyBranchScheduler(self):
        from buildbot.scheduler import AnyBranchScheduler
        assert AnyBranchScheduler

    def test_scheduler_basic_Dependent(self):
        from buildbot.schedulers.basic import Dependent
        assert Dependent

    def test_scheduler_Dependent(self):
        from buildbot.scheduler import Dependent
        assert Dependent

    def test_scheduler_Periodic(self):
        from buildbot.scheduler import Periodic
        assert Periodic

    def test_scheduler_Nightly(self):
        from buildbot.scheduler import Nightly
        assert Nightly

    def test_scheduler_Triggerable(self):
        from buildbot.scheduler import Triggerable
        assert Triggerable

    def test_scheduler_Try_Jobdir(self):
        from buildbot.scheduler import Try_Jobdir
        assert Try_Jobdir

    def test_scheduler_Try_Userpass(self):
        from buildbot.scheduler import Try_Userpass
        assert Try_Userpass

    def test_changes_changes_ChangeMaster(self):
        # this must exist to open old changes pickles
        from buildbot.changes.changes import ChangeMaster
        assert ChangeMaster

    def test_changes_changes_Change(self):
        # this must exist to open old changes pickles
        from buildbot.changes.changes import Change
        assert Change

    def test_status_html_Webstatus(self):
        from buildbot.status.html import WebStatus
        assert WebStatus

    def test_schedulers_filter_ChangeFilter(self):
        # this was the location of ChangeFilter until 0.8.4
        from buildbot.schedulers.filter import ChangeFilter
        assert ChangeFilter

    def test_process_base_Build(self):
        from buildbot.process.base import Build
        assert Build

    def test_buildrequest_BuildRequest(self):
        from buildbot.buildrequest import BuildRequest
        assert BuildRequest

    def test_sourcestamp_SourceStamp(self):
        # this must exist, and the class must be defined at this package path,
        # in order for old build pickles to be loaded.
        from buildbot.sourcestamp import SourceStamp
        assert SourceStamp

    def test_process_subunitlogobserver_SubunitShellCommand(self):
        from buildbot.process.subunitlogobserver import SubunitShellCommand
        assert SubunitShellCommand

    def test_status_builder_results(self):
        # these symbols are now in buildbot.status.results, but lots of user
        # code references them here:
        from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, SKIPPED
        from buildbot.status.builder import EXCEPTION, RETRY, Results
        from buildbot.status.builder import worst_status
        # reference the symbols to avoid failure from pyflakes
        (SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY, Results,
         worst_status)

    def test_status_builder_BuildStepStatus(self):
        from buildbot.status.builder import BuildStepStatus
        assert BuildStepStatus

    def test_status_builder_BuildSetStatus(self):
        from buildbot.status.builder import BuildSetStatus
        assert BuildSetStatus

    def test_status_builder_TestResult(self):
        from buildbot.status.builder import TestResult
        assert TestResult

    def test_status_builder_LogFile(self):
        from buildbot.status.builder import LogFile
        assert LogFile

    def test_status_builder_HTMLLogFile(self):
        from buildbot.status.builder import HTMLLogFile
        assert HTMLLogFile

    def test_status_builder_SlaveStatus(self):
        from buildbot.status.builder import SlaveStatus
        assert SlaveStatus

    def test_status_builder_Status(self):
        from buildbot.status.builder import Status
        assert Status

    def test_status_builder_Event(self):
        from buildbot.status.builder import Event
        assert Event

    def test_status_builder_BuildStatus(self):
        from buildbot.status.builder import BuildStatus
        assert BuildStatus

    def test_steps_source_Source(self):
        from buildbot.steps.source import Source
        assert Source

    @deprecatedImport
    def test_steps_source_CVS(self):
        from buildbot.steps.source import CVS
        assert CVS

    @deprecatedImport
    def test_steps_source_SVN(self):
        from buildbot.steps.source import SVN
        assert SVN

    @deprecatedImport
    def test_steps_source_Git(self):
        from buildbot.steps.source import Git
        assert Git

    @deprecatedImport
    def test_steps_source_Darcs(self):
        from buildbot.steps.source import Darcs
        assert Darcs

    @deprecatedImport
    def test_steps_source_Repo(self):
        from buildbot.steps.source import Repo
        assert Repo

    @deprecatedImport
    def test_steps_source_Bzr(self):
        from buildbot.steps.source import Bzr
        assert Bzr

    @deprecatedImport
    def test_steps_source_Mercurial(self):
        from buildbot.steps.source import Mercurial
        assert Mercurial

    @deprecatedImport
    def test_steps_source_P4(self):
        from buildbot.steps.source import P4
        assert P4

    @deprecatedImport
    def test_steps_source_Monotone(self):
        from buildbot.steps.source import Monotone
        assert Monotone

    @deprecatedImport
    def test_steps_source_BK(self):
        from buildbot.steps.source import BK
        assert BK
