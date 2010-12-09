
"""
Test the PB change source.
"""

from twisted.trial.unittest import TestCase
from twisted.spread.pb import IPerspective
from twisted.cred.credentials import UsernamePassword
from twisted.python.filepath import FilePath

from buildbot.master import BuildMaster
from buildbot.changes.pb import ChangePerspective, PBChangeSource

class TestPBChangeSource(TestCase):
    """
    Tests for PBChangeSource.
    """
    def setUp(self):
        """
        Create an unstarted BuildMaster instance with a PBChangeSource as a
        child.
        """
        self.username = 'alice'
        self.password = 'sekret'
        path = FilePath(self.mktemp())
        path.makedirs()
        self.master = BuildMaster(path.path)
        self.master.readConfig = True # XXX OPPOSITE DAY
        self.change_source = PBChangeSource(self.username, self.password)
        self.master.change_svc.addSource(self.change_source)


    def test_authentication(self):
        """
        After the BuildMaster service starts, the PBChangeSource's credentials
        are accepted by the master's credentials checker.
        """
        self.master.startService()
        d = self.master.checker.requestAvatarId(
            UsernamePassword(self.username, self.password))
        def checkUsername(result):
            self.assertEquals(result, self.username)
        d.addCallback(checkUsername)
        return d


    def test_authorization(self):
        """
        After the BuildMaster service starts, a ChangePerspective can be
        retrieved from the master's dispatcher (realm) with the PBChangeSource's
        username (avatar identifier).
        """
        self.master.startService()
        d = self.master.dispatcher.requestAvatar(
            self.username, None, IPerspective)
        def checkLogin((interface, avatar, logout)):
            self.assertIdentical(interface, IPerspective)
            self.assertIsInstance(avatar, ChangePerspective)
        d.addCallback(checkLogin)
        return d


