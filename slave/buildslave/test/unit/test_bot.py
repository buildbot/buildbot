import os
import shutil

from twisted.trial import unittest
from twisted.internet import defer
from zope.interface import implements

import buildslave
from buildslave import bot
from buildslave.test.util import fakeremote

class TestBot(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        self.real_bot = bot.Bot(self.basedir, False)
        self.real_bot.startService()

        self.bot = fakeremote.FakeRemote(self.real_bot)

    def tearDown(self):
        d = defer.succeed(None)
        if self.real_bot and self.real_bot.running:
            d.addCallback(lambda _ : self.real_bot.stopService())
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

    def test_setBuilderList_empty(self):
        d = self.bot.callRemote("setBuilderList", [])
        def check(builders):
            self.assertEqual(builders, {})
        d.addCallback(check)
        return d

