import mock
from twisted.internet import defer

class ChangeSourceMixin(object):
    """
    Set up a fake ChangeMaster (C{self.changemaster}) and handle starting and
    stopping a ChangeSource service.  All Change objects added with
    C{addChange} appear at C{self.changes_added}.
    """

    changesource = None

    def setupChangeSource(self):
        self.changemaster = mock.Mock()

        self.changes_added = []
        def addChange(change):
            self.changes_added.append(change)
        self.changemaster.addChange = addChange

        return defer.succeed(None)

    def tearDownChangeSource(self):
        if not self.changesource:
            return defer.succeed(None)
        return defer.maybeDeferred(self.changesource.stopService)

    def startChangeSource(self, cs):
        """Call this after constructing your changeSource; returns a deferred."""
        self.changesource = cs
        cs.parent = self.changemaster
        cs.startService()
        return defer.succeed(None)
