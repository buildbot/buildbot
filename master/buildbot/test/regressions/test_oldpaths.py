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

    def test_process_subunitlogobserver_SubunitShellCommand(self):
        from buildbot.process.subunitlogobserver import SubunitShellCommand
        assert SubunitShellCommand

    def test_status_builder_results(self):
        # these symbols are now in buildbot.process.results, but lots of user
        # code references them here:
        from buildbot.status.builder import SUCCESS, WARNINGS, FAILURE, SKIPPED
        from buildbot.status.builder import EXCEPTION, RETRY, Results
        from buildbot.status.builder import worst_status
        # reference the symbols to avoid failure from pyflakes
        (SUCCESS, WARNINGS, FAILURE, SKIPPED, EXCEPTION, RETRY, Results,
         worst_status)

    def test_status_builder_BuildSetStatus(self):
        from buildbot.status.builder import BuildSetStatus
        assert BuildSetStatus

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

    def test_buildstep_remotecommand(self):
        from buildbot.process.buildstep import RemoteCommand, \
            LoggedRemoteCommand, RemoteShellCommand
        assert RemoteCommand
        assert LoggedRemoteCommand
        assert RemoteShellCommand

    def test_buildstep_logobserver(self):
        from buildbot.process.buildstep import LogObserver, \
            LogLineObserver, OutputProgressObserver
        assert LogObserver
        assert LogLineObserver
        assert OutputProgressObserver
