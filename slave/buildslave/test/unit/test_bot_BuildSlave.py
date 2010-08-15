import os
import shutil

from twisted.trial import unittest
from twisted.spread import pb
from twisted.internet import reactor, defer
from twisted.cred import checkers, portal
from zope.interface import implements

from buildslave import bot

# I don't see any simple way to test the PB equipment without actually setting
# up a TCP connection.  This just tests that the PB code will connect and can
# execute a basic ping.  The rest is done without TCP (or PB) in other test modules.

class MasterPerspective(pb.Avatar):
    def __init__(self, fire_on_keepalive=None):
        self.fire_on_keepalive = fire_on_keepalive

    def perspective_keepalive(self):
        if self.fire_on_keepalive:
            d = self.fire_on_keepalive
            self.fire_on_keepalive = None
            d.callback(None)

class MasterRealm:
    def __init__(self, perspective, on_attachment):
        self.perspective = perspective
        self.on_attachment = on_attachment

    implements(portal.IRealm)
    def requestAvatar(self, avatarId, mind, *interfaces):
        assert pb.IPerspective in interfaces
        self.perspective.mind = mind
        d = defer.succeed(None)
        if self.on_attachment:
            d.addCallback(lambda _: self.on_attachment(mind))
        def returnAvatar(_):
            return pb.IPerspective, self.perspective, lambda: None
        d.addCallback(returnAvatar)
        return d

class TestBuildSlave(unittest.TestCase):

    def setUp(self):
        self.buildslave = None
        self.listeningport = None

        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

    def tearDown(self):
        d = defer.succeed(None)
        if self.buildslave and self.buildslave.running:
            d.addCallback(lambda _ : self.buildslave.stopService())
        if self.listeningport:
            d.addCallback(lambda _ : self.listeningport.stopListening())
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        return d

    def start_master(self, perspective, on_attachment=None):
        self.realm = MasterRealm(perspective, on_attachment)
        p = portal.Portal(self.realm)
        p.registerChecker(
            checkers.InMemoryUsernamePasswordDatabaseDontUse(testy="westy"))
        self.listeningport = reactor.listenTCP(0, pb.PBServerFactory(p))
        # return the dynamically allocated port number
        return self.listeningport.socket.getsockname()[1]

    def test_keepalive_called(self):
        # set up to call this deferred on receipt of a keepalive
        d = defer.Deferred()
        persp = MasterPerspective(fire_on_keepalive=d)

        # start up the master and slave, with a very short keepalive
        port = self.start_master(persp)
        self.buildslave = bot.BuildSlave("localhost", port,
                "testy", "westy", self.basedir,
                keepalive=0.1, keepaliveTimeout=0.05, usePTY=False)
        self.buildslave.startService()

        # and wait for it to keepalive
        return d

    def test_buildslave_print(self):
        d = defer.Deferred()

        # set up to call print when we are attached, and chain the results onto
        # the deferred for the whole test
        def call_print(mind):
            print_d = mind.callRemote("print", "Hi, slave.")
            print_d.addCallbacks(d.callback, d.errback)

        # start up the master and slave, with a very short keepalive
        persp = MasterPerspective()
        port = self.start_master(persp, on_attachment=call_print)
        self.buildslave = bot.BuildSlave("localhost", port,
                "testy", "westy", self.basedir,
                keepalive=0, usePTY=False, umask=022)
        self.buildslave.startService()

        # and wait for the result of the print
        return d
