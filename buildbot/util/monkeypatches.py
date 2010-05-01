from twisted.trial import unittest

def add_debugging_monkeypatches():
    """
    DO NOT CALL THIS DIRECTLY

    This adds a few "harmless" monkeypatches which make it easier to debug
    failing tests.  It is called automatically by buildbot.test.__init__.
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

    # make unittest.TestCase have a patch method, even if it just skips
    # the test.
    def nopatch(self, *args):
        raise unittest.SkipTest('unittest.patch is not available')
    if not hasattr(unittest.TestCase, 'patch'):
        unittest.TestCase.patch = nopatch
