import sys

import twisted
from twisted.trial import unittest

def add_debugging_monkeypatches():
    """
    DO NOT CALL THIS DIRECTLY

    This adds a few "harmless" monkeypatches which make it easier to debug
    failing tests.
    """
    from twisted.application.service import Service
    old_startService = Service.startService
    old_stopService = Service.stopService
    def startService(self):
        assert not self.running
        return old_startService(self)
    def stopService(self):
        assert self.running
        return old_stopService(self)
    Service.startService = startService
    Service.stopService = stopService

    # versions of Twisted before 9.0.0 did not have a UnitTest.patch that worked
    # on Python-2.7
    if twisted.version.major <= 9 and sys.version_info[:2] == (2,7):
        def nopatch(self, *args):
            raise unittest.SkipTest('unittest.patch is not available')
        unittest.TestCase.patch = nopatch

add_debugging_monkeypatches()

__all__ = []
