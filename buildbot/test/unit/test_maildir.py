# -*- test-case-name: buildbot.test.test_maildir -*-

from twisted.trial import unittest
import os, shutil
from buildbot.changes.mail import FCMaildirSource
from twisted.internet import defer, reactor, task
from twisted.python import util, log

class TimeOutError(Exception):
    """The message were not received in a timely fashion"""

class MaildirTest(unittest.TestCase):
    SECONDS_PER_MESSAGE = 1.0

    def setUp(self):
        log.msg("creating empty maildir")
        self.maildir = "test-maildir"
        if os.path.isdir(self.maildir):
            shutil.rmtree(self.maildir)
            log.msg("removing stale maildir")
        os.mkdir(self.maildir)
        os.mkdir(os.path.join(self.maildir, "cur"))
        os.mkdir(os.path.join(self.maildir, "new"))
        os.mkdir(os.path.join(self.maildir, "tmp"))
        self.source = None

    def tearDown(self):
        log.msg("removing old maildir")
        shutil.rmtree(self.maildir)
        if self.source:
            return self.source.stopService()

    def addChange(self, c):
        # NOTE: this assumes every message results in a Change, which isn't
        # true for msg8-prefix
        log.msg("got change")
        self.changes.append(c)

    def deliverMail(self, msg):
        log.msg("delivering", msg)
        newdir = os.path.join(self.maildir, "new")
        # to do this right, use safecat
        shutil.copy(msg, newdir)

    def poll(self, changes, count, d):
        if len(changes) == count:
            d.callback("passed")

    def testMaildir(self):
        self.changes = []
        s = self.source = FCMaildirSource(self.maildir)
        s.parent = self
        s.startService()
        testfiles_dir = util.sibpath(__file__, "mail")
        testfiles = [msg for msg in os.listdir(testfiles_dir)
                     if msg.startswith("freshcvs")]
        assert testfiles
        testfiles.sort()
        count = len(testfiles)
        d = defer.Deferred()

        i = 1
        for i in range(count):
            msg = testfiles[i]
            reactor.callLater(self.SECONDS_PER_MESSAGE*i, self.deliverMail,
                              os.path.join(testfiles_dir, msg))
        self.loop = task.LoopingCall(self.poll, self.changes, count, d)
        self.loop.start(0.1)
        t = reactor.callLater(self.SECONDS_PER_MESSAGE*count + 15,
                              d.errback, TimeOutError)
        # TODO: verify the messages, should use code from test_mailparse but
        # I'm not sure how to factor the verification routines out in a
        # useful fashion

        #for i in range(count):
        #    msg, check = test_messages[i]
        #    check(self, self.changes[i])

        def _shutdown(res):
            if t.active():
                t.cancel()
            self.loop.stop()
            return res
        d.addBoth(_shutdown)

        return d

    # TODO: it would be nice to set this timeout after counting the number of
    # messages in buildbot/test/mail/msg*, but I suspect trial wants to have
    # this number before the method starts, and maybe even before setUp()
    testMaildir.timeout = SECONDS_PER_MESSAGE*9 + 15

