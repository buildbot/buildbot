import os
import shutil

from twisted.trial import unittest
from twisted.internet import defer, reactor
from twisted.python import failure, log
from zope.interface import implements
import mock

from buildslave.test.util import command
from buildslave.test.fake.remote import FakeRemote
from buildslave.test.fake.runprocess import Expect
import buildslave
from buildslave import bot

class TestBot(unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        self.real_bot = bot.Bot(self.basedir, False)
        self.real_bot.startService()

        self.bot = FakeRemote(self.real_bot)

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

class FakeStep(object):
    "A fake master-side BuildStep that records its activities."
    def __init__(self):
        self.finished_d = defer.Deferred()
        self.actions = []

    def wait_for_finish(self):
        return self.finished_d

    def remote_update(self, updates):
        self.actions.append(["update", updates])

    def remote_complete(self, f):
        self.actions.append(["complete", f])
        self.finished_d.callback(None)

class TestSlaveBuilder(command.CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.basedir = os.path.abspath("basedir")
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        os.makedirs(self.basedir)

        self.bot = bot.Bot(self.basedir, False)
        self.bot.startService()

        # get a SlaveBuilder object from the bot and wrap it as a fake remote
        builders = self.bot.remote_setBuilderList([('sb', 'sb')])
        self.sb = FakeRemote(builders['sb'])

        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

        d = defer.succeed(None)
        if self.bot and self.bot.running:
            d.addCallback(lambda _ : self.bot.stopService())
        if os.path.exists(self.basedir):
            shutil.rmtree(self.basedir)
        return d

    def test_print(self):
        return self.sb.callRemote("print", "Hello, SlaveBuilder.")

    def test_setMaster(self):
        # not much to check here - what the SlaveBuilder does with the
        # master is not part of the interface (and, in fact, it does very little)
        return self.sb.callRemote("setMaster", mock.Mock())

    def test_shutdown(self):
        # don't *actually* shut down the reactor - that would be silly
        self.patch(bot.SlaveBuilder, "_reactor", mock.Mock())
        d = self.sb.callRemote("shutdown")
        def check(_):
            self.assertTrue(bot.SlaveBuilder._reactor.stop.called)
        d.addCallback(check)
        return d

    def test_startBuild(self):
        return self.sb.callRemote("startBuild")

    def test_startCommand(self):
        # set up a fake step to receive updates
        st = FakeStep()

        # patch runprocess to handle the 'echo', below
        self.patch_runprocess(
            Expect([ 'echo', 'hello' ], os.path.join(self.basedir, 'sb', 'workdir'))
            + { 'hdr' : 'headers' } + { 'stdout' : 'hello\n' } + { 'rc' : 0 }
            + 0,
        )

        d = defer.succeed(None)
        def do_start(_):
            return self.sb.callRemote("startCommand", FakeRemote(st),
                                      "13", "shell", dict(
                                                command=[ 'echo', 'hello' ],
                                                workdir='workdir',
                                            ))
        d.addCallback(do_start)
        d.addCallback(lambda _ : st.wait_for_finish())
        def check(_):
            self.assertEqual(st.actions, [
                         ['update', [[{'hdr': 'headers'}, 0]]],
                         ['update', [[{'stdout': 'hello\n'}, 0]]],
                         ['update', [[{'rc': 0}, 0]]],
                         ['complete', None],
                    ])
        d.addCallback(check)
        return d

    def test_startCommand_interruptCommand(self):
        # set up a fake step to receive updates
        st = FakeStep()

        # patch runprocess to pretend to sleep (it will really just hang forever,
        # except that we interrupt it)
        self.patch_runprocess(
            Expect([ 'sleep', '10' ], os.path.join(self.basedir, 'sb', 'workdir'))
            + { 'hdr' : 'headers' }
            + { 'wait' : True }
        )

        d = defer.succeed(None)
        def do_start(_):
            return self.sb.callRemote("startCommand", FakeRemote(st),
                                      "13", "shell", dict(
                                                command=[ 'sleep', '10' ],
                                                workdir='workdir',
                                            ))
        d.addCallback(do_start)

        # wait a jiffy..
        def do_wait(_):
            d = defer.Deferred()
            reactor.callLater(0.01, d.callback, None)
            return d
        d.addCallback(do_wait)

        # and then interrupt the step
        def do_interrupt(_):
            return self.sb.callRemote("interruptCommand", "13", "tl/dr")
        d.addCallback(do_interrupt)

        d.addCallback(lambda _ : st.wait_for_finish())
        def check(_):
            self.assertEqual(st.actions, [
                         ['update', [[{'hdr': 'headers'}, 0]]],
                         ['update', [[{'hdr': 'killing'}, 0]]],
                         ['update', [[{'rc': -1}, 0]]],
                         ['complete', None],
                    ])
        d.addCallback(check)
        return d

    def test_startCommand_failure(self):
        # similar to test_startCommand, but leave out some args so the slave
        # generates a failure

        # set up a fake step to receive updates
        st = FakeStep()

        # patch the log.err, otherwise trial will think something *actually* failed
        self.patch(log, "err", lambda f : None)

        d = defer.succeed(None)
        def do_start(_):
            return self.sb.callRemote("startCommand", FakeRemote(st),
                                      "13", "shell", dict(
                                                workdir='workdir',
                                            ))
        d.addCallback(do_start)
        d.addCallback(lambda _ : st.wait_for_finish())
        def check(_):
            self.assertEqual(st.actions[0][0], 'complete')
            self.assertTrue(isinstance(st.actions[0][1], failure.Failure))
        d.addCallback(check)
        return d
