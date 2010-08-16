import os
import shutil

from twisted.trial import unittest
from twisted.spread import pb
from twisted.internet import reactor, defer
from twisted.cred import checkers, portal
from zope.interface import implements

import buildslave
from buildslave import bot

class TestBot(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        self.bot = bot.Bot(self.basedir, False)
        self.bot.startService()

        # patch on a callRemote method
        def callRemote(meth, *args, **kwargs):
            fn = getattr(self.bot, "remote_" + meth)
            return defer.maybeDeferred(fn, *args, **kwargs)
        self.bot.callRemote = callRemote

    def tearDown(self):
        d = defer.succeed(None)
        if self.bot and self.bot.running:
            d.addCallback(lambda _ : self.bot.stopService())
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        return d

    def test_getCommands(self):
        d = self.bot.callRemote("getCommands")
        def check(cmds):
            # just check that 'shell' is present..
            self.assertTrue('shell' in cmds)
        d.addCallback(check)
        return d

    def test_getVersion(self):
        d = self.bot.callRemote("getVersion")
        def check(vers):
            self.assertEqual(vers, buildslave.version)
        d.addCallback(check)
        return d

    def test_getSlaveInfo(self):
        infodir = os.path.join(self.basedir, "info")
        os.makedirs(infodir)
        open(os.path.join(infodir, "admin"), "w").write("testy!")
        open(os.path.join(infodir, "foo"), "w").write("bar")

        d = self.bot.callRemote("getSlaveInfo")
        def check(info):
            self.assertEqual(info, dict(admin='testy!', foo='bar'))
        d.addCallback(check)
        return d

    def test_getSlaveInfo_nodir(self):
        d = self.bot.callRemote("getSlaveInfo")
        def check(info):
            self.assertEqual(info, {})
        d.addCallback(check)
        return d
