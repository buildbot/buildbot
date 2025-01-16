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

from buildbot.test.util.warnings import assertProducesWarnings
from buildbot.warnings import DeprecatedApiWarning


def deprecatedImport(fn):
    def wrapper(self):
        fn(self)
        warnings = self.flushWarnings()
        # on older Pythons, this warning appears twice, so use collapse it
        if len(warnings) == 2 and warnings[0] == warnings[1]:
            del warnings[1]
        self.assertEqual(len(warnings), 1, f"got: {warnings!r}")
        self.assertEqual(warnings[0]['category'], DeprecatedApiWarning)

    return wrapper


class OldImportPaths(unittest.TestCase):
    """
    Test that old, deprecated import paths still work.
    """

    def test_scheduler_Scheduler(self):
        from buildbot.scheduler import Scheduler  # noqa: F401

    def test_schedulers_basic_Scheduler(self):
        # renamed to basic.SingleBranchScheduler
        from buildbot.schedulers.basic import Scheduler  # noqa: F401

    def test_scheduler_AnyBranchScheduler(self):
        from buildbot.scheduler import AnyBranchScheduler  # noqa: F401

    def test_scheduler_basic_Dependent(self):
        with assertProducesWarnings(DeprecationWarning, message_pattern='.*was deprecated.*'):
            from buildbot.schedulers.basic import Dependent  # noqa: F401

    def test_scheduler_Dependent(self):
        from buildbot.scheduler import Dependent  # noqa: F401

    def test_scheduler_Periodic(self):
        from buildbot.scheduler import Periodic  # noqa: F401

    def test_scheduler_Nightly(self):
        from buildbot.scheduler import Nightly  # noqa: F401

    def test_scheduler_Triggerable(self):
        from buildbot.scheduler import Triggerable  # noqa: F401

    def test_scheduler_Try_Jobdir(self):
        from buildbot.scheduler import Try_Jobdir  # noqa: F401

    def test_scheduler_Try_Userpass(self):
        from buildbot.scheduler import Try_Userpass  # noqa: F401

    def test_schedulers_filter_ChangeFilter(self):
        # this was the location of ChangeFilter until 0.8.4
        from buildbot.schedulers.filter import ChangeFilter  # noqa: F401

    def test_process_base_Build(self):
        from buildbot.process.base import Build  # noqa: F401

    def test_buildrequest_BuildRequest(self):
        from buildbot.buildrequest import BuildRequest  # noqa: F401

    def test_process_subunitlogobserver_SubunitShellCommand(self):
        from buildbot.process.subunitlogobserver import SubunitShellCommand  # noqa: F401

    def test_steps_source_Source(self):
        from buildbot.steps.source import Source  # noqa: F401
