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

    def test_setBuilderList_single(self):
        d = self.bot.callRemote("setBuilderList", [ ('mybld', 'myblddir') ])
        def check(builders):
            self.assertEqual(builders.keys(), ['mybld'])
            self.assertTrue(os.path.exists(os.path.join(self.basedir, 'myblddir')))
            # note that we test the SlaveBuilder instance below
        d.addCallback(check)
        return d

    def test_setBuilderList_updates(self):
        d = defer.succeed(None)

        slavebuilders = {}

        def add_my(_):
            d = self.bot.callRemote("setBuilderList", [
                        ('mybld', 'myblddir') ])
            def check(builders):
                self.assertEqual(builders.keys(), ['mybld'])
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'myblddir')))
                slavebuilders['my'] = builders['mybld']
            d.addCallback(check)
            return d
        d.addCallback(add_my)

        def add_your(_):
            d = self.bot.callRemote("setBuilderList", [
                        ('mybld', 'myblddir'), ('yourbld', 'yourblddir') ])
            def check(builders):
                self.assertEqual(sorted(builders.keys()), sorted(['mybld', 'yourbld']))
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'myblddir')))
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'yourblddir')))
                # 'my' should still be the same slavebuilder object
                self.assertEqual(id(slavebuilders['my']), id(builders['mybld']))
                slavebuilders['your'] = builders['yourbld']
            d.addCallback(check)
            return d
        d.addCallback(add_your)

        def remove_my(_):
            d = self.bot.callRemote("setBuilderList", [
                        ('yourbld', 'yourblddir2') ]) # note new builddir
            def check(builders):
                self.assertEqual(sorted(builders.keys()), sorted(['yourbld']))
                # note that build dirs are not deleted..
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'myblddir')))
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'yourblddir')))
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'yourblddir2')))
                # 'your' should still be the same slavebuilder object
                self.assertEqual(id(slavebuilders['your']), id(builders['yourbld']))
            d.addCallback(check)
            return d
        d.addCallback(remove_my)

        def add_and_remove(_):
            d = self.bot.callRemote("setBuilderList", [
                        ('theirbld', 'theirblddir') ])
            def check(builders):
                self.assertEqual(sorted(builders.keys()), sorted(['theirbld']))
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'myblddir')))
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'yourblddir')))
                self.assertTrue(os.path.exists(os.path.join(self.basedir, 'theirblddir')))
            d.addCallback(check)
            return d
        d.addCallback(add_and_remove)

        return d
