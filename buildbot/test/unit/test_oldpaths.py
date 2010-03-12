import types

from twisted.trial import unittest

class OldImportPaths(unittest.TestCase):
    """
    Test that old, deprecated import paths still work.
    """

    def test_scheduler_Scheduler(self):
        from buildbot.scheduler import Scheduler

    def test_scheduler_AnyBranchScheduler(self):
        from buildbot.scheduler import AnyBranchScheduler

    def test_scheduler_Dependent(self):
        from buildbot.scheduler import Dependent

    def test_scheduler_Periodic(self):
        from buildbot.scheduler import Periodic

    def test_scheduler_Nightly(self):
        from buildbot.scheduler import Nightly

    def test_scheduler_Triggerable(self):
        from buildbot.scheduler import Triggerable

    def test_scheduler_Try_Jobdir(self):
        from buildbot.scheduler import Try_Jobdir

    def test_scheduler_Try_Userpass(self):
        from buildbot.scheduler import Try_Userpass
