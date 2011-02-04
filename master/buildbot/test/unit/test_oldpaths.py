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

class OldImportPaths(unittest.TestCase):
    """
    Test that old, deprecated import paths still work.
    """

    def test_scheduler_Scheduler(self):
        from buildbot.scheduler import Scheduler
        assert Scheduler

    def test_scheduler_AnyBranchScheduler(self):
        from buildbot.scheduler import AnyBranchScheduler
        assert AnyBranchScheduler

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
