
"""
Test the PB change source.
"""

from twisted.trial.unittest import TestCase
from twisted.spread.pb import IPerspective
from twisted.cred.credentials import UsernamePassword

from buildbot.master import BotMaster
from buildbot.changes.pb import ChangePerspective, PBChangeSource

class TestPBChangeSource(TestCase):
    """
    Tests for PBChangeSource.
    """
    def setUp(self):
        """
        Create an unstarted BotMaster instance with a PBChangeSource as a child.
        """
        self.username = 'alice'
        self.password = 'sekret'
        self.master = BotMaster()
        self.change_source = PBChangeSource(self.username, self.password)
        self.master.change_svc.addSource(self.change_source)


    def test_authentication(self):
        """
        After the BotMaster service starts, the PBChangeSource's credentials are
        accepted by the master's credentials checker.
        """
        self.master.startService()
        self.assertEquals(
            self.master.checker.requestAvatarId(
                UsernamePassword(self.username, self.password)),
            self.username)


    def test_authorization(self):
        """
        After the BotMaster service starts, a ChangePerspective can be retrieved
        from the master's dispatcher (realm) with the PBChangeSource's username
        (avatar identifier).
        """
        self.master.startService()
        perspective = self.master.dispatcher.requestAvatar(
            self.username, None, IPerspective)
        self.assertIsInstance(perspective, ChangePerspective)

