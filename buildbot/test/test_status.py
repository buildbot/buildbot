# -*- test-case-name: buildbot.test.test_status -*-

import email, os
import operator

from zope.interface import implements
from twisted.internet import defer, reactor
from twisted.trial import unittest

from buildbot import interfaces
from buildbot.sourcestamp import SourceStamp
from buildbot.process.base import BuildRequest, Build
from buildbot.status import builder, base, words, progress
from buildbot.changes.changes import Change
from buildbot.process.builder import Builder
from time import sleep

import sys
if sys.version_info[:3] < (2,4,0):
    from sets import Set as set

mail = None
try:
    from buildbot.status import mail
except ImportError:
    pass
from buildbot.status import progress, client # NEEDS COVERAGE
from buildbot.test.runutils import RunMixin, setupBuildStepStatus, rmtree

class MyStep:
    build = None
    def getName(self):
        return "step"
    def getResults(self):
        return (builder.SUCCESS, "yay")

class MyLogFileProducer(builder.LogFileProducer):
    # The reactor.callLater(0) in LogFileProducer.resumeProducing is a bit of
    # a nuisance from a testing point of view. This subclass adds a Deferred
    # to that call so we can find out when it is complete.
    def resumeProducing(self):
        d = defer.Deferred()
        reactor.callLater(0, self._resumeProducing, d)
        return d
    def _resumeProducing(self, d):
        builder.LogFileProducer._resumeProducing(self)
        reactor.callLater(0, d.callback, None)

class MyLog(builder.LogFile):
    def __init__(self, basedir, name, text=None, step=None):
        self.fakeBuilderBasedir = basedir
        if not step:
            step = MyStep()
        builder.LogFile.__init__(self, step, name, name)
        if text:
            self.addStdout(text)
            self.finish()
    def getFilename(self):
        return os.path.join(self.fakeBuilderBasedir, self.name)

    def subscribeConsumer(self, consumer):
        p = MyLogFileProducer(self, consumer)
        d = p.resumeProducing()
        return d

class MyHTMLLog(builder.HTMLLogFile):
    def __init__(self, basedir, name, html):
        step = MyStep()
        builder.HTMLLogFile.__init__(self, step, name, name, html)

class MyLogSubscriber:
    def __init__(self):
        self.chunks = []
    def logChunk(self, build, step, log, channel, text):
        self.chunks.append((channel, text))

class MyLogConsumer:
    def __init__(self, limit=None):
        self.chunks = []
        self.finished = False
        self.limit = limit
    def registerProducer(self, producer, streaming):
        self.producer = producer
        self.streaming = streaming
    def unregisterProducer(self):
        self.producer = None
    def writeChunk(self, chunk):
        self.chunks.append(chunk)
        if self.limit:
            self.limit -= 1
            if self.limit == 0:
                self.producer.pauseProducing()
    def finish(self):
        self.finished = True

if mail:
    class MyMailer(mail.MailNotifier):
        def sendMessage(self, m, recipients):
            self.parent.messages.append((m, recipients))

class MyStatus:
    def getBuildbotURL(self):
        return self.url
    def getURLForThing(self, thing):
        return None
    def getProjectName(self):
        return "myproj"

class MyBuilder(builder.BuilderStatus):
    nextBuildNumber = 0

class MyBuild(builder.BuildStatus):
    testlogs = []
    def __init__(self, parent, number, results):
        builder.BuildStatus.__init__(self, parent, number)
        self.results = results
        self.source = SourceStamp(revision="1.14")
        self.reason = "build triggered by changes"
        self.finished = True
    def getLogs(self):
        return self.testlogs

class MyLookup:
    implements(interfaces.IEmailLookup)

    def getAddress(self, user):
        d = defer.Deferred()
        # With me now is Mr Thomas Walters of West Hartlepool who is totally
        # invisible.
        if user == "Thomas_Walters":
            d.callback(None)
        else:
            d.callback(user + "@" + "dev.com")
        return d

def customTextMailMessage(attrs):
    logLines = 3
    text = list()
    text.append("STATUS: %s" % attrs['result'].title())
    text.append("")
    text.extend([c.asText() for c in attrs['changes']])
    text.append("")
    name, url, lines, status = attrs['logs'][-1]
    text.append("Last %d lines of '%s':" % (logLines, name))
    text.extend(["\t%s\n" % line for line in lines[len(lines)-logLines:]])
    text.append("")
    text.append("Build number was: %s" % attrs['buildProperties']['buildnumber'])
    text.append("")
    text.append("-buildbot")
    return ("\n".join(text), 'plain')

def customHTMLMailMessage(attrs):
    logLines = 3
    text = list()
    text.append("<h3>STATUS <a href='%s'>%s</a>:</h3>" % (attrs['buildURL'],
                                                          attrs['result'].title()))
    text.append("<h4>Recent Changes:</h4>")
    text.extend([c.asHTML() for c in attrs['changes']])
    name, url, lines, status = attrs['logs'][-1]
    text.append("<h4>Last %d lines of '%s':</h4>" % (logLines, name))
    text.append("<p>")
    text.append("<br>".join([line for line in lines[len(lines)-logLines:]]))
    text.append("</p>")
    text.append("<p>Build number was: %s</p>" % attrs['buildProperties']['buildnumber'])
    text.append("<br>")
    text.append("<b>-<a href='%s'>buildbot</a></b>" % attrs['buildbotURL'])
    return ("\n".join(text), 'html')

class Mail(unittest.TestCase):

    def setUp(self):
        self.builder = MyBuilder("builder1")

    def stall(self, res, timeout):
        d = defer.Deferred()
        reactor.callLater(timeout, d.callback, res)
        return d

    def makeBuild(self, number, results):
        return MyBuild(self.builder, number, results)

    def failUnlessIn(self, substring, string):
        self.failUnless(string.find(substring) != -1,
                        "didn't see '%s' in '%s'" % (substring, string))

    def getProjectName(self):
        return "PROJECT"

    def getBuildbotURL(self):
        return "BUILDBOT_URL"

    def getURLForThing(self, thing):
        return None

    def testBuild1(self):
        mailer = MyMailer(fromaddr="buildbot@example.com",
                          extraRecipients=["recip@example.com",
                                           "recip2@example.com"],
                          lookup=mail.Domain("dev.com"))
        mailer.parent = self
        mailer.master_status = self
        self.messages = []

        b1 = self.makeBuild(3, builder.SUCCESS)
        b1.blamelist = ["bob"]

        mailer.buildFinished("builder1", b1, b1.results)
        self.failUnless(len(self.messages) == 1)
        m,r = self.messages.pop()
        t = m.as_string()
        self.failUnlessIn("To: bob@dev.com\n", t)
        self.failUnlessIn("CC: recip2@example.com, recip@example.com\n", t)
        self.failUnlessIn("From: buildbot@example.com\n", t)
        self.failUnlessIn("Subject: buildbot success in PROJECT on builder1\n", t)
        self.failUnlessIn("Date: ", t)
        self.failUnlessIn("Build succeeded!\n", t)
        self.failUnlessIn("Buildbot URL: BUILDBOT_URL\n", t)

    def testBuild2(self):
        mailer = MyMailer(fromaddr="buildbot@example.com",
                          extraRecipients=["recip@example.com",
                                           "recip2@example.com"],
                          lookup="dev.com",
                          sendToInterestedUsers=False)
        mailer.parent = self
        mailer.master_status = self
        self.messages = []

        b1 = self.makeBuild(3, builder.SUCCESS)
        b1.blamelist = ["bob"]

        mailer.buildFinished("builder1", b1, b1.results)
        self.failUnless(len(self.messages) == 1)
        m,r = self.messages.pop()
        t = m.as_string()
        self.failUnlessIn("To: recip2@example.com, "
                          "recip@example.com\n", t)
        self.failUnlessIn("From: buildbot@example.com\n", t)
        self.failUnlessIn("Subject: buildbot success in PROJECT on builder1\n", t)
        self.failUnlessIn("Build succeeded!\n", t)
        self.failUnlessIn("Buildbot URL: BUILDBOT_URL\n", t)

    def testBuildStatusCategory(self):
        # a status client only interested in a category should only receive
        # from that category
        mailer = MyMailer(fromaddr="buildbot@example.com",
                          extraRecipients=["recip@example.com",
                                           "recip2@example.com"],
                          lookup="dev.com",
                          sendToInterestedUsers=False,
                          categories=["debug"])

        mailer.parent = self
        mailer.master_status = self
        self.messages = []

        b1 = self.makeBuild(3, builder.SUCCESS)
        b1.blamelist = ["bob"]

        mailer.buildFinished("builder1", b1, b1.results)
        self.failIf(self.messages)

    def testBuilderCategory(self):
        # a builder in a certain category should notify status clients that
        # did not list categories, or categories including this one
        mailer1 = MyMailer(fromaddr="buildbot@example.com",
                           extraRecipients=["recip@example.com",
                                            "recip2@example.com"],
                           lookup="dev.com",
                           sendToInterestedUsers=False)
        mailer2 = MyMailer(fromaddr="buildbot@example.com",
                           extraRecipients=["recip@example.com",
                                            "recip2@example.com"],
                           lookup="dev.com",
                           sendToInterestedUsers=False,
                           categories=["active"])
        mailer3 = MyMailer(fromaddr="buildbot@example.com",
                           extraRecipients=["recip@example.com",
                                            "recip2@example.com"],
                           lookup="dev.com",
                           sendToInterestedUsers=False,
                           categories=["active", "debug"])

        builderd = MyBuilder("builder2", "debug")

        mailer1.parent = self
        mailer1.master_status = self
        mailer2.parent = self
        mailer2.master_status = self
        mailer3.parent = self
        mailer3.master_status = self
        self.messages = []

        t = mailer1.builderAdded("builder2", builderd)
        self.assertEqual(len(mailer1.watched), 1)
        self.assertEqual(t, mailer1)
        t = mailer2.builderAdded("builder2", builderd)
        self.assertEqual(len(mailer2.watched), 0)
        self.assertEqual(t, None)
        t = mailer3.builderAdded("builder2", builderd)
        self.assertEqual(len(mailer3.watched), 1)
        self.assertEqual(t, mailer3)

        b2 = MyBuild(builderd, 3, builder.SUCCESS)
        b2.blamelist = ["bob"]

        mailer1.buildFinished("builder2", b2, b2.results)
        self.failUnlessEqual(len(self.messages), 1)
        self.messages = []
        mailer2.buildFinished("builder2", b2, b2.results)
        self.failUnlessEqual(len(self.messages), 0)
        self.messages = []
        mailer3.buildFinished("builder2", b2, b2.results)
        self.failUnlessEqual(len(self.messages), 1)

    def testCustomTextMessage(self):
        basedir = "test_custom_text_mesg"
        os.mkdir(basedir)
        mailer = MyMailer(fromaddr="buildbot@example.com", mode="problem",
                          extraRecipients=["recip@example.com",
                                           "recip2@example.com"],
                          lookup=MyLookup(),
                          customMesg=customTextMailMessage)
        mailer.parent = self
        mailer.master_status = self
        self.messages = []

        b1 = self.makeBuild(4, builder.FAILURE)
        b1.setProperty('buildnumber', 1, 'Build')
        b1.setText(["snarkleack", "polarization", "failed"])
        b1.blamelist = ["dev3", "dev3", "dev3", "dev4",
                        "Thomas_Walters"]
        b1.source.changes = (Change(who = 'author1', files = ['file1'], comments = 'comment1', revision = 123),
                             Change(who = 'author2', files = ['file2'], comments = 'comment2', revision = 456))
        b1.testlogs = [MyLog(basedir, 'compile', "Compile log here\n"),
                       MyLog(basedir, 'test', "Test log here\nTest 1 failed\nTest 2 failed\nTest 3 failed\nTest 4 failed\n")]

        mailer.buildFinished("builder1", b1, b1.results)
        m,r = self.messages.pop()
        t = m.as_string()
        #
        # Uncomment to review custom message
        #
        #self.fail(t)
        self.failUnlessIn("comment1", t)
        self.failUnlessIn("comment2", t)
        self.failUnlessIn("Test 4 failed", t)
        self.failUnlessIn("number was: 1", t)


    def testCustomHTMLMessage(self):
        basedir = "test_custom_HTML_mesg"
        os.mkdir(basedir)
        mailer = MyMailer(fromaddr="buildbot@example.com", mode="problem",
                          extraRecipients=["recip@example.com",
                                           "recip2@example.com"],
                          lookup=MyLookup(),
                          customMesg=customHTMLMailMessage)
        mailer.parent = self
        mailer.master_status = self
        self.messages = []

        b1 = self.makeBuild(4, builder.FAILURE)
        b1.setProperty('buildnumber', 1, 'Build')
        b1.setText(["snarkleack", "polarization", "failed"])
        b1.blamelist = ["dev3", "dev3", "dev3", "dev4",
                        "Thomas_Walters"]
        b1.source.changes = (Change(who = 'author1', files = ['file1'], comments = 'comment1', revision = 123),
                             Change(who = 'author2', files = ['file2'], comments = 'comment2', revision = 456))
        b1.testlogs = [MyLog(basedir, 'compile', "Compile log here\n"),
                       MyLog(basedir, 'test', "Test log here\nTest 1 failed\nTest 2 failed\nTest 3 failed\nTest 4 failed\n")]

        mailer.buildFinished("builder1", b1, b1.results)
        m,r = self.messages.pop()
        t = m.as_string()
        #
        # Uncomment to review custom message
        #
        #self.fail(t)
        self.failUnlessIn("<h4>Last 3 lines of 'step.test':</h4>", t)
        self.failUnlessIn("<p>Changed by: <b>author2</b><br />", t)
        self.failUnlessIn("Test 3 failed", t)
        self.failUnlessIn("number was: 1", t)

    def testShouldAttachLog(self):
        mailer = mail.MailNotifier(fromaddr="buildbot@example.com", addLogs=True)
        self.assertTrue(mailer._shouldAttachLog('anything'))
        mailer = mail.MailNotifier(fromaddr="buildbot@example.com", addLogs=False)
        self.assertFalse(mailer._shouldAttachLog('anything'))
        mailer = mail.MailNotifier(fromaddr="buildbot@example.com", addLogs=['something'])
        self.assertFalse(mailer._shouldAttachLog('anything'))
        self.assertTrue(mailer._shouldAttachLog('something'))

    def testShouldAttachPatches(self):
        basedir = "test_should_attach_patches"
        os.mkdir(basedir)
        b1 = self.makeBuild(4, builder.FAILURE)
        b1.setProperty('buildnumber', 1, 'Build')
        b1.setText(["snarkleack", "polarization", "failed"])
        b1.blamelist = ["dev3", "dev3", "dev3", "dev4",
                        "Thomas_Walters"]
        b1.source.changes = (Change(who = 'author1', files = ['file1'], comments = 'comment1', revision = 123),
                             Change(who = 'author2', files = ['file2'], comments = 'comment2', revision = 456))
        b1.testlogs = [MyLog(basedir, 'compile', "Compile log here\n"),
                       MyLog(basedir, 'test', "Test log here\nTest 1 failed\nTest 2 failed\nTest 3 failed\nTest 4 failed\n")]
        b1.source.patch = (0, '--- /dev/null\n+++ a_file\n', None)

        mailer = MyMailer(fromaddr="buildbot@example.com", addPatch=True)
        mailer.parent = self
        mailer.master_status = self
        self.messages = []
        mailer.buildFinished("builder1", b1, b1.results)
        m,r = self.messages.pop()
        self.assertTrue(m.is_multipart())
        self.assertEqual(len([True for i in m.walk()]), 3)

        mailer = MyMailer(fromaddr="buildbot@example.com", addPatch=False)
        mailer.parent = self
        mailer.master_status = self
        self.messages = []
        mailer.buildFinished("builder1", b1, b1.results)
        m,r = self.messages.pop()
        self.assertFalse(m.is_multipart())
        self.assertEqual(len([True for i in m.walk()]), 1)

        mailer = MyMailer(fromaddr="buildbot@example.com")
        mailer.parent = self
        mailer.master_status = self
        self.messages = []
        mailer.buildFinished("builder1", b1, b1.results)
        m,r = self.messages.pop()
        self.assertTrue(m.is_multipart())
        self.assertEqual(len([True for i in m.walk()]), 3)


    def testFailure(self):
        mailer = MyMailer(fromaddr="buildbot@example.com", mode="problem",
                          extraRecipients=["recip@example.com",
                                           "recip2@example.com"],
                          lookup=MyLookup())
        mailer.parent = self
        mailer.master_status = self
        self.messages = []

        b1 = self.makeBuild(3, builder.SUCCESS)
        b1.blamelist = ["dev1", "dev2"]
        b2 = self.makeBuild(4, builder.FAILURE)
        b2.setText(["snarkleack", "polarization", "failed"])
        b2.blamelist = ["dev3", "dev3", "dev3", "dev4",
                        "Thomas_Walters"]
        mailer.buildFinished("builder1", b1, b1.results)
        self.failIf(self.messages)
        mailer.buildFinished("builder1", b2, b2.results)
        self.failUnless(len(self.messages) == 1)
        m,r = self.messages.pop()
        t = m.as_string()
        self.failUnlessIn("To: dev3@dev.com, dev4@dev.com\n", t)
        self.failUnlessIn("CC: recip2@example.com, recip@example.com\n", t)
        self.failUnlessIn("From: buildbot@example.com\n", t)
        self.failUnlessIn("Subject: buildbot failure in PROJECT on builder1\n", t)
        self.failUnlessIn("The Buildbot has detected a new failure", t)
        self.failUnlessIn("BUILD FAILED: snarkleack polarization failed\n", t)
        self.failUnlessEqual(set(r), set(["dev3@dev.com", "dev4@dev.com",
                                 "recip2@example.com", "recip@example.com"]))

    
    def testChange(self):
        raise unittest.SkipTest("TODO: Fix Build/Builder mock objects to support getPrevBuild()")
    
        mailer = MyMailer(fromaddr="buildbot@example.com", mode="change",
                          extraRecipients=["bah@bah.bah"],
                          lookup=MyLookup())
        mailer.parent = self
        mailer.master_status = self
        self.messages = []
        
        b1 = self.makeBuild(1, builder.SUCCESS)
        b2 = self.makeBuild(2, builder.SUCCESS)
        b3 = self.makeBuild(3, builder.FAILURE)
        b4 = self.makeBuild(4, builder.FAILURE)
        b5 = self.makeBuild(5, builder.SUCCESS)
        b6 = self.makeBuild(6, builder.SUCCESS)
        
        # no message on first or repetetive success
        mailer.buildFinished("builder1", b1, b1.results)
        self.failIf(self.messages)
        mailer.buildFinished("builder1", b2, b2.results)
        self.failIf(self.messages)
        
        # message on first fail only
        mailer.buildFinished("builder1", b3, b3.results)
        self.failUnless(len(self.messages) == 1)
        self.messages.pop()
        mailer.buildFinished("builder1", b4, b4.results)
        self.failIf(self.messages)

        # message on first following success
        mailer.buildFinished("builder1", b5, b5.results)
        self.failUnless(len(self.messages) == 1)
        self.messages.pop()
        mailer.buildFinished("builder1", b6, b6.results)
        self.failIf(self.messages)


    def testLogs(self):
        basedir = "test_status_logs"
        os.mkdir(basedir)
        mailer = MyMailer(fromaddr="buildbot@example.com", addLogs=True,
                          extraRecipients=["recip@example.com",
                                           "recip2@example.com"])
        mailer.parent = self
        mailer.master_status = self
        self.messages = []

        b1 = self.makeBuild(3, builder.WARNINGS)
        b1.testlogs = [MyLog(basedir, 'compile', "Compile log here\n"),
                       MyLog(basedir,
                             'test', "Test log here\nTest 4 failed\n"),
                   ]
        b1.text = ["unusual", "gnarzzler", "output"]
        mailer.buildFinished("builder1", b1, b1.results)
        self.failUnless(len(self.messages) == 1)
        m,r = self.messages.pop()
        t = m.as_string()
        self.failUnlessIn("Subject: buildbot warnings in PROJECT on builder1\n", t)
        m2 = email.message_from_string(t)
        p = m2.get_payload()
        self.failUnlessEqual(len(p), 3)

        self.failUnlessIn("Build Had Warnings: unusual gnarzzler output\n",
                          p[0].get_payload())

        self.failUnlessEqual(p[1].get_filename(), "step.compile")
        self.failUnlessEqual(p[1].get_payload(), "Compile log here\n")
        
        self.failUnlessEqual(p[2].get_filename(), "step.test")
        self.failUnlessIn("Test log here\n", p[2].get_payload())

    def testMail(self):
        basedir = "test_status_mail"
        os.mkdir(basedir)
        dest = os.environ.get("BUILDBOT_TEST_MAIL")
        if not dest:
            raise unittest.SkipTest("define BUILDBOT_TEST_MAIL=dest to run this")
        mailer = mail.MailNotifier(fromaddr="buildbot@example.com",
                                   addLogs=True,
                                   extraRecipients=[dest])
        s = MyStatus()
        s.url = "project URL"
        mailer.master_status = s

        b1 = self.makeBuild(3, builder.SUCCESS)
        b1.testlogs = [MyLog(basedir, 'compile', "Compile log here\n"),
                       MyLog(basedir,
                             'test', "Test log here\nTest 4 failed\n"),
                   ]

        d = mailer.buildFinished("builder1", b1, b1.results)
        # When this fires, the mail has been sent, but the SMTP connection is
        # still up (because smtp.sendmail relies upon the server to hang up).
        # Spin for a moment to avoid the "unclean reactor" warning that Trial
        # gives us if we finish before the socket is disconnected. Really,
        # sendmail() ought to hang up the connection once it is finished:
        # otherwise a malicious SMTP server could make us consume lots of
        # memory.
        d.addCallback(self.stall, 0.1)
        return d

if not mail:
    Mail.skip = "the Twisted Mail package is not installed"

class Progress(unittest.TestCase):
    def testWavg(self):
        bp = progress.BuildProgress([])
        e = progress.Expectations(bp)
        # wavg(old, current)
        self.failUnlessEqual(e.wavg(None, None), None)
        self.failUnlessEqual(e.wavg(None, 3), 3)
        self.failUnlessEqual(e.wavg(3, None), 3)
        self.failUnlessEqual(e.wavg(3, 4), 3.5)
        e.decay = 0.1
        self.failUnlessEqual(e.wavg(3, 4), 3.1)


class Results(unittest.TestCase):

    def testAddResults(self):
        b = builder.BuildStatus(builder.BuilderStatus("test"), 12)
        testname = ("buildbot", "test", "test_status", "Results",
                    "testAddResults")
        r1 = builder.TestResult(name=testname,
                                results=builder.SUCCESS,
                                text=["passed"],
                                logs={'output': ""},
                                )
        b.addTestResult(r1)

        res = b.getTestResults()
        self.failUnlessEqual(res.keys(), [testname])
        t = res[testname]
        self.failUnless(interfaces.ITestResult.providedBy(t))
        self.failUnlessEqual(t.getName(), testname)
        self.failUnlessEqual(t.getResults(), builder.SUCCESS)
        self.failUnlessEqual(t.getText(), ["passed"])
        self.failUnlessEqual(t.getLogs(), {'output': ""})

class Log(unittest.TestCase):
    basedir = "status_log_add"

    def setUp(self):
        self.tearDown()
        os.mkdir(self.basedir)

    def tearDown(self):
        if os.path.exists(self.basedir):
            rmtree(self.basedir)

    def testAdd(self):
        l = MyLog(self.basedir, "compile", step=13)
        self.failUnlessEqual(l.getName(), "compile")
        self.failUnlessEqual(l.getStep(), 13)
        l.addHeader("HEADER\n")
        l.addStdout("Some text\n")
        l.addStderr("Some error\n")
        l.addStdout("Some more text\n")
        self.failIf(l.isFinished())
        l.finish()
        self.failUnless(l.isFinished())
        self.failUnlessEqual(l.getText(),
                             "Some text\nSome error\nSome more text\n")
        self.failUnlessEqual(l.getTextWithHeaders(),
                             "HEADER\n" +
                             "Some text\nSome error\nSome more text\n")
        self.failUnlessEqual(len(list(l.getChunks())), 4)

        self.failUnless(l.hasContents())
        try:
            os.unlink(l.getFilename())
        except OSError:
            os.unlink(l.getFilename() + ".bz2")
        self.failIf(l.hasContents())

    def TODO_testDuplicate(self):
        # create multiple logs for the same step with the same logname, make
        # sure their on-disk filenames are suitably uniquified. This
        # functionality actually lives in BuildStepStatus and BuildStatus, so
        # this test must involve more than just the MyLog class.

        # naieve approach, doesn't work
        l1 = MyLog(self.basedir, "duplicate")
        l1.addStdout("Some text\n")
        l1.finish()
        l2 = MyLog(self.basedir, "duplicate")
        l2.addStdout("Some more text\n")
        l2.finish()
        self.failIfEqual(l1.getFilename(), l2.getFilename())

    def testMerge1(self):
        l = MyLog(self.basedir, "merge1")
        l.addHeader("HEADER\n")
        l.addStdout("Some text\n")
        l.addStdout("Some more text\n")
        l.addStdout("more\n")
        l.finish()
        self.failUnlessEqual(l.getText(),
                             "Some text\nSome more text\nmore\n")
        self.failUnlessEqual(l.getTextWithHeaders(),
                             "HEADER\n" +
                             "Some text\nSome more text\nmore\n")
        self.failUnlessEqual(len(list(l.getChunks())), 2)

    def testMerge2(self):
        l = MyLog(self.basedir, "merge2")
        l.addHeader("HEADER\n")
        for i in xrange(1000):
            l.addStdout("aaaa")
        for i in xrange(30):
            l.addStderr("bbbb")
        for i in xrange(10):
            l.addStdout("cc")
        target = 1000*"aaaa" + 30 * "bbbb" + 10 * "cc"
        self.failUnlessEqual(len(l.getText()), len(target))
        self.failUnlessEqual(l.getText(), target)
        l.finish()
        self.failUnlessEqual(len(l.getText()), len(target))
        self.failUnlessEqual(l.getText(), target)
        self.failUnlessEqual(len(list(l.getChunks())), 4)

    def testMerge3(self):
        l = MyLog(self.basedir, "merge3")
        l.chunkSize = 100
        l.addHeader("HEADER\n")
        for i in xrange(8):
            l.addStdout(10*"a")
        for i in xrange(8):
            l.addStdout(10*"a")
        self.failUnlessEqual(list(l.getChunks()),
                             [(builder.HEADER, "HEADER\n"),
                              (builder.STDOUT, 100*"a"),
                              (builder.STDOUT, 60*"a")])
        l.finish()
        self.failUnlessEqual(l.getText(), 160*"a")

    def testReadlines(self):
        l = MyLog(self.basedir, "chunks1")
        l.addHeader("HEADER\n") # should be ignored
        l.addStdout("Some text\n")
        l.addStdout("Some More Text\nAnd Some More\n")
        l.addStderr("Some Stderr\n")
        l.addStdout("Last line\n")
        l.finish()
        alllines = list(l.readlines())
        self.failUnlessEqual(len(alllines), 4)
        self.failUnlessEqual(alllines[0], "Some text\n")
        self.failUnlessEqual(alllines[2], "And Some More\n")
        self.failUnlessEqual(alllines[3], "Last line\n")
        stderr = list(l.readlines(interfaces.LOG_CHANNEL_STDERR))
        self.failUnlessEqual(len(stderr), 1)
        self.failUnlessEqual(stderr[0], "Some Stderr\n")
        lines = l.readlines()
        if False: # TODO: l.readlines() is not yet an iterator
            # verify that it really is an iterator
            line0 = lines.next()
            self.failUnlessEqual(line0, "Some text\n")
            line1 = lines.next()
            line2 = lines.next()
            self.failUnlessEqual(line2, "And Some More\n")


    def testChunks(self):
        l = MyLog(self.basedir, "chunks2")
        c1 = l.getChunks()
        l.addHeader("HEADER\n")
        l.addStdout("Some text\n")
        self.failUnlessEqual("".join(l.getChunks(onlyText=True)),
                             "HEADER\nSome text\n")
        c2 = l.getChunks()

        l.addStdout("Some more text\n")
        self.failUnlessEqual("".join(l.getChunks(onlyText=True)),
                             "HEADER\nSome text\nSome more text\n")
        c3 = l.getChunks()
        
        l.addStdout("more\n")
        l.finish()

        self.failUnlessEqual(list(c1), [])
        self.failUnlessEqual(list(c2), [(builder.HEADER, "HEADER\n"),
                                        (builder.STDOUT, "Some text\n")])
        self.failUnlessEqual(list(c3), [(builder.HEADER, "HEADER\n"),
                                        (builder.STDOUT,
                                         "Some text\nSome more text\n")])
        
        self.failUnlessEqual(l.getText(),
                             "Some text\nSome more text\nmore\n")
        self.failUnlessEqual(l.getTextWithHeaders(),
                             "HEADER\n" +
                             "Some text\nSome more text\nmore\n")
        self.failUnlessEqual(len(list(l.getChunks())), 2)

    def testUpgrade(self):
        l = MyLog(self.basedir, "upgrade")
        l.addHeader("HEADER\n")
        l.addStdout("Some text\n")
        l.addStdout("Some more text\n")
        l.addStdout("more\n")
        l.finish()
        self.failUnless(l.hasContents())
        # now doctor it to look like a 0.6.4-era non-upgraded logfile
        l.entries = list(l.getChunks())
        del l.filename
        try:
            os.unlink(l.getFilename() + ".bz2")
        except OSError:
            os.unlink(l.getFilename())
        # now make sure we can upgrade it
        l.upgrade("upgrade")
        self.failUnlessEqual(l.getText(),
                             "Some text\nSome more text\nmore\n")
        self.failUnlessEqual(len(list(l.getChunks())), 2)
        self.failIf(l.entries)

        # now, do it again, but make it look like an upgraded 0.6.4 logfile
        # (i.e. l.filename is missing, but the contents are there on disk)
        l.entries = list(l.getChunks())
        del l.filename
        l.upgrade("upgrade")
        self.failUnlessEqual(l.getText(),
                             "Some text\nSome more text\nmore\n")
        self.failUnlessEqual(len(list(l.getChunks())), 2)
        self.failIf(l.entries)
        self.failUnless(l.hasContents())

    def testHTMLUpgrade(self):
        l = MyHTMLLog(self.basedir, "upgrade", "log contents")
        l.upgrade("filename")

    def testSubscribe(self):
        l1 = MyLog(self.basedir, "subscribe1")
        l1.finish()
        self.failUnless(l1.isFinished())

        s = MyLogSubscriber()
        l1.subscribe(s, True)
        l1.unsubscribe(s)
        self.failIf(s.chunks)

        s = MyLogSubscriber()
        l1.subscribe(s, False)
        l1.unsubscribe(s)
        self.failIf(s.chunks)

        finished = []
        l2 = MyLog(self.basedir, "subscribe2")
        l2.waitUntilFinished().addCallback(finished.append)
        l2.addHeader("HEADER\n")
        s1 = MyLogSubscriber()
        l2.subscribe(s1, True)
        s2 = MyLogSubscriber()
        l2.subscribe(s2, False)
        self.failUnlessEqual(s1.chunks, [(builder.HEADER, "HEADER\n")])
        self.failUnlessEqual(s2.chunks, [])

        l2.addStdout("Some text\n")
        self.failUnlessEqual(s1.chunks, [(builder.HEADER, "HEADER\n"),
                                         (builder.STDOUT, "Some text\n")])
        self.failUnlessEqual(s2.chunks, [(builder.STDOUT, "Some text\n")])
        l2.unsubscribe(s1)
        
        l2.addStdout("Some more text\n")
        self.failUnlessEqual(s1.chunks, [(builder.HEADER, "HEADER\n"),
                                         (builder.STDOUT, "Some text\n")])
        self.failUnlessEqual(s2.chunks, [(builder.STDOUT, "Some text\n"),
                                         (builder.STDOUT, "Some more text\n"),
                                         ])
        self.failIf(finished)
        l2.finish()
        self.failUnlessEqual(finished, [l2])

    def testConsumer(self):
        l1 = MyLog(self.basedir, "consumer1")
        l1.finish()
        self.failUnless(l1.isFinished())

        s = MyLogConsumer()
        d = l1.subscribeConsumer(s)
        d.addCallback(self._testConsumer_1, s)
        return d
    testConsumer.timeout = 5
    def _testConsumer_1(self, res, s):
        self.failIf(s.chunks)
        self.failUnless(s.finished)
        self.failIf(s.producer) # producer should be registered and removed

        l2 = MyLog(self.basedir, "consumer2")
        l2.addHeader("HEADER\n")
        l2.finish()
        self.failUnless(l2.isFinished())

        s = MyLogConsumer()
        d = l2.subscribeConsumer(s)
        d.addCallback(self._testConsumer_2, s)
        return d
    def _testConsumer_2(self, res, s):
        self.failUnlessEqual(s.chunks, [(builder.HEADER, "HEADER\n")])
        self.failUnless(s.finished)
        self.failIf(s.producer) # producer should be registered and removed


        l2 = MyLog(self.basedir, "consumer3")
        l2.chunkSize = 1000
        l2.addHeader("HEADER\n")
        l2.addStdout(800*"a")
        l2.addStdout(800*"a") # should now have two chunks on disk, 1000+600
        l2.addStdout(800*"b") # HEADER,1000+600*a on disk, 800*a in memory
        l2.addStdout(800*"b") # HEADER,1000+600*a,1000+600*b on disk
        l2.addStdout(200*"c") # HEADER,1000+600*a,1000+600*b on disk,
                              # 200*c in memory
        
        s = MyLogConsumer(limit=1)
        d = l2.subscribeConsumer(s)
        d.addCallback(self._testConsumer_3, l2, s)
        return d
    def _testConsumer_3(self, res, l2, s):
        self.failUnless(s.streaming)
        self.failUnlessEqual(s.chunks, [(builder.HEADER, "HEADER\n")])
        s.limit = 1
        d = s.producer.resumeProducing()
        d.addCallback(self._testConsumer_4, l2, s)
        return d
    def _testConsumer_4(self, res, l2, s):
        self.failUnlessEqual(s.chunks, [(builder.HEADER, "HEADER\n"),
                                        (builder.STDOUT, 1000*"a"),
                                        ])
        s.limit = None
        d = s.producer.resumeProducing()
        d.addCallback(self._testConsumer_5, l2, s)
        return d
    def _testConsumer_5(self, res, l2, s):
        self.failUnlessEqual(s.chunks, [(builder.HEADER, "HEADER\n"),
                                        (builder.STDOUT, 1000*"a"),
                                        (builder.STDOUT, 600*"a"),
                                        (builder.STDOUT, 1000*"b"),
                                        (builder.STDOUT, 600*"b"),
                                        (builder.STDOUT, 200*"c")])
        l2.addStdout(1000*"c") # HEADER,1600*a,1600*b,1200*c on disk
        self.failUnlessEqual(s.chunks, [(builder.HEADER, "HEADER\n"),
                                        (builder.STDOUT, 1000*"a"),
                                        (builder.STDOUT, 600*"a"),
                                        (builder.STDOUT, 1000*"b"),
                                        (builder.STDOUT, 600*"b"),
                                        (builder.STDOUT, 200*"c"),
                                        (builder.STDOUT, 1000*"c")])
        l2.finish()
        self.failUnlessEqual(s.chunks, [(builder.HEADER, "HEADER\n"),
                                        (builder.STDOUT, 1000*"a"),
                                        (builder.STDOUT, 600*"a"),
                                        (builder.STDOUT, 1000*"b"),
                                        (builder.STDOUT, 600*"b"),
                                        (builder.STDOUT, 200*"c"),
                                        (builder.STDOUT, 1000*"c")])
        self.failIf(s.producer)
        self.failUnless(s.finished)

    def testLargeSummary(self):
        bigtext = "a" * 200000 # exceed the NetstringReceiver 100KB limit
        l = MyLog(self.basedir, "large", bigtext)
        s = MyLogConsumer()
        d = l.subscribeConsumer(s)
        def _check(res):
            for ctype,chunk in s.chunks:
                self.failUnless(len(chunk) < 100000)
            merged = "".join([c[1] for c in s.chunks])
            self.failUnless(merged == bigtext)
        d.addCallback(_check)
        # when this fails, it fails with a timeout, and there is an exception
        # sent to log.err(). This AttributeError exception is in
        # NetstringReceiver.dataReceived where it does
        # self.transport.loseConnection() because of the NetstringParseError,
        # however self.transport is None
        return d
    testLargeSummary.timeout = 5

    def testLimit(self):
        l = MyLog(self.basedir, "limit")
        l.logMaxSize = 150
        for i in range(1000):
            l.addStdout("Some data")
        l.finish()
        t = l.getText()
        # Compare against 175 since we truncate logs based on chunks, so we may
        # go slightly over the limit
        self.failIf(len(t) > 175, "Text too long (%i)" % len(t))
        self.failUnless("truncated" in l.getTextWithHeaders(),
                "No truncated message found")

class CompressLog(unittest.TestCase):
    # compression is not supported unless bz2 is installed
    try:
        import bz2
    except:
        skip = "compression not supported (no bz2 module available)"

    def testCompressLogs(self):
        bss = setupBuildStepStatus("test-compress")
        bss.build.builder.setLogCompressionLimit(1024)
        l = bss.addLog('not-compress')
        l.addStdout('a' * 512)
        l.finish()
        lc = bss.addLog('to-compress')
        lc.addStdout('b' * 1024)
        lc.finish()
        d = bss.stepFinished(builder.SUCCESS)
        self.failUnless(d is not None)
        d.addCallback(self._verifyCompression, bss)
        return d

    def _verifyCompression(self, result, bss):
        self.failUnless(len(bss.getLogs()), 2)
        (ncl, cl) = bss.getLogs() # not compressed, compressed log
        self.failUnless(os.path.isfile(ncl.getFilename()))
        self.failIf(os.path.isfile(ncl.getFilename() + ".bz2"))
        self.failIf(os.path.isfile(cl.getFilename()))
        self.failUnless(os.path.isfile(cl.getFilename() + ".bz2"))
        content = ncl.getText()
        self.failUnless(len(content), 512)
        content = cl.getText()
        self.failUnless(len(content), 1024)
        pass

config_base = """
from buildbot.process import factory
from buildbot.steps import dummy
from buildbot.buildslave import BuildSlave
from buildbot.config import BuilderConfig
s = factory.s

f1 = factory.QuickBuildFactory('fakerep', 'cvsmodule', configure=None)

f2 = factory.BuildFactory([
    s(dummy.Dummy, timeout=1),
    s(dummy.RemoteDummy, timeout=2),
    ])

BuildmasterConfig = c = {}
c['slaves'] = [BuildSlave('bot1', 'sekrit')]
c['schedulers'] = []
c['builders'] = [
    BuilderConfig(name='quick', slavename='bot1', factory=f1),
]
c['slavePortnum'] = 0
"""

config_2 = config_base + """
c['builders'] = [
    BuilderConfig(name='dummy', slavename='bot1', factory=f2),
    BuilderConfig(name='testdummy', slavename='bot1',
                  factory=f2, category='test'),
]
"""

class STarget(base.StatusReceiver):
    debug = False

    def __init__(self, mode):
        self.mode = mode
        self.events = []
    def announce(self):
        if self.debug:
            print self.events[-1]

    def builderAdded(self, name, builder):
        self.events.append(("builderAdded", name, builder))
        self.announce()
        if "builder" in self.mode:
            return self
    def builderChangedState(self, name, state):
        self.events.append(("builderChangedState", name, state))
        self.announce()
    def buildStarted(self, name, build):
        self.events.append(("buildStarted", name, build))
        self.announce()
        if "eta" in self.mode:
            self.eta_build = build.getETA()
        if "build" in self.mode:
            return self
    def buildETAUpdate(self, build, ETA):
        self.events.append(("buildETAUpdate", build, ETA))
        self.announce()
    def stepStarted(self, build, step):
        self.events.append(("stepStarted", build, step))
        self.announce()
        if 0 and "eta" in self.mode:
            print "TIMES", step.getTimes()
            print "ETA", step.getETA()
            print "EXP", step.getExpectations()
        if "step" in self.mode:
            return self
    def stepTextChanged(self, build, step, text):
        self.events.append(("stepTextChanged", step, text))
    def stepText2Changed(self, build, step, text2):
        self.events.append(("stepText2Changed", step, text2))
    def stepETAUpdate(self, build, step, ETA, expectations):
        self.events.append(("stepETAUpdate", build, step, ETA, expectations))
        self.announce()
    def logStarted(self, build, step, log):
        self.events.append(("logStarted", build, step, log))
        self.announce()
    def logFinished(self, build, step, log):
        self.events.append(("logFinished", build, step, log))
        self.announce()
    def stepFinished(self, build, step, results):
        self.events.append(("stepFinished", build, step, results))
        if 0 and "eta" in self.mode:
            print "post-EXP", step.getExpectations()
        self.announce()
    def buildFinished(self, name, build, results):
        self.events.append(("buildFinished", name, build, results))
        self.announce()
    def builderRemoved(self, name):
        self.events.append(("builderRemoved", name))
        self.announce()

class Subscription(RunMixin, unittest.TestCase):
    # verify that StatusTargets can subscribe/unsubscribe properly

    def testSlave(self):
        m = self.master
        s = m.getStatus()
        self.t1 = t1 = STarget(["builder"])
        #t1.debug = True; print
        s.subscribe(t1)
        self.failUnlessEqual(len(t1.events), 0)

        self.t3 = t3 = STarget(["builder", "build", "step"])
        s.subscribe(t3)

        m.loadConfig(config_2)
        m.readConfig = True
        m.startService()

        self.failUnlessEqual(len(t1.events), 4)
        self.failUnlessEqual(t1.events[0][0:2], ("builderAdded", "dummy"))
        self.failUnlessEqual(t1.events[1],
                             ("builderChangedState", "dummy", "offline"))
        self.failUnlessEqual(t1.events[2][0:2], ("builderAdded", "testdummy"))
        self.failUnlessEqual(t1.events[3],
                             ("builderChangedState", "testdummy", "offline"))
        t1.events = []

        self.failUnlessEqual(s.getBuilderNames(), ["dummy", "testdummy"])
        self.failUnlessEqual(s.getBuilderNames(categories=['test']),
                             ["testdummy"])
        self.s1 = s1 = s.getBuilder("dummy")
        self.failUnlessEqual(s1.getName(), "dummy")
        self.failUnlessEqual(s1.getState(), ("offline", []))
        self.failUnlessEqual(s1.getCurrentBuilds(), [])
        self.failUnlessEqual(s1.getLastFinishedBuild(), None)
        self.failUnlessEqual(s1.getBuild(-1), None)
        #self.failUnlessEqual(s1.getEvent(-1), foo("created"))

        # status targets should, upon being subscribed, immediately get a
        # list of all current builders matching their category
        self.t2 = t2 = STarget([])
        s.subscribe(t2)
        self.failUnlessEqual(len(t2.events), 2)
        self.failUnlessEqual(t2.events[0][0:2], ("builderAdded", "dummy"))
        self.failUnlessEqual(t2.events[1][0:2], ("builderAdded", "testdummy"))

        d = self.connectSlave(builders=["dummy", "testdummy"])
        d.addCallback(self._testSlave_1, t1)
        return d

    def _testSlave_1(self, res, t1):
        self.failUnlessEqual(len(t1.events), 2)
        self.failUnlessEqual(t1.events[0],
                             ("builderChangedState", "dummy", "idle"))
        self.failUnlessEqual(t1.events[1],
                             ("builderChangedState", "testdummy", "idle"))
        t1.events = []

        c = interfaces.IControl(self.master)
        req = BuildRequest("forced build for testing", SourceStamp(), 'test_builder')
        c.getBuilder("dummy").requestBuild(req)
        d = req.waitUntilFinished()
        d2 = self.master.botmaster.waitUntilBuilderIdle("dummy")
        dl = defer.DeferredList([d, d2])
        dl.addCallback(self._testSlave_2)
        return dl

    def _testSlave_2(self, res):
        # t1 subscribes to builds, but not anything lower-level
        ev = self.t1.events
        self.failUnlessEqual(len(ev), 4)
        self.failUnlessEqual(ev[0][0:3],
                             ("builderChangedState", "dummy", "building"))
        self.failUnlessEqual(ev[1][0], "buildStarted")
        self.failUnlessEqual(ev[2][0:2]+ev[2][3:4],
                             ("buildFinished", "dummy", builder.SUCCESS))
        self.failUnlessEqual(ev[3][0:3],
                             ("builderChangedState", "dummy", "idle"))

        self.failUnlessEqual([ev[0] for ev in self.t3.events],
                             ["builderAdded",
                              "builderChangedState", # offline
                              "builderAdded",
                              "builderChangedState", # idle
                              "builderChangedState", # offline
                              "builderChangedState", # idle
                              "builderChangedState", # building
                              "buildStarted",
                              "stepStarted", "stepETAUpdate", 
                              "stepTextChanged", "stepFinished",
                              "stepStarted", "stepETAUpdate",
                              "stepTextChanged", "logStarted", "logFinished",
                              "stepTextChanged", "stepText2Changed",
                              "stepFinished",
                              "buildFinished",
                              "builderChangedState", # idle
                              ])

        b = self.s1.getLastFinishedBuild()
        self.failUnless(b)
        self.failUnlessEqual(b.getBuilder().getName(), "dummy")
        self.failUnlessEqual(b.getNumber(), 0)
        self.failUnlessEqual(b.getSourceStamp().branch, None)
        self.failUnlessEqual(b.getSourceStamp().patch, None)
        self.failUnlessEqual(b.getSourceStamp().revision, None)
        self.failUnlessEqual(b.getReason(), "forced build for testing")
        self.failUnlessEqual(b.getChanges(), ())
        self.failUnlessEqual(b.getResponsibleUsers(), [])
        self.failUnless(b.isFinished())
        self.failUnlessEqual(b.getText(), ['build', 'successful'])
        self.failUnlessEqual(b.getResults(), builder.SUCCESS)

        steps = b.getSteps()
        self.failUnlessEqual(len(steps), 2)

        eta = 0
        st1 = steps[0]
        self.failUnlessEqual(st1.getName(), "dummy")
        self.failUnless(st1.isFinished())
        self.failUnlessEqual(st1.getText(), ["delay", "1 secs"])
        start,finish = st1.getTimes()
        self.failUnless(0.5 < (finish-start) < 10)
        self.failUnlessEqual(st1.getExpectations(), [])
        self.failUnlessEqual(st1.getLogs(), [])
        eta += finish-start

        st2 = steps[1]
        self.failUnlessEqual(st2.getName(), "remote dummy")
        self.failUnless(st2.isFinished())
        self.failUnlessEqual(st2.getText(),
                             ["remote", "delay", "2 secs"])
        start,finish = st2.getTimes()
        self.failUnless(1.5 < (finish-start) < 10)
        eta += finish-start
        self.failUnlessEqual(st2.getExpectations(), [('output', 38, None)])
        logs = st2.getLogs()
        self.failUnlessEqual(len(logs), 1)
        self.failUnlessEqual(logs[0].getName(), "stdio")
        self.failUnlessEqual(logs[0].getText(), "data")

        self.eta = eta
        # now we run it a second time, and we should have an ETA

        self.t4 = t4 = STarget(["builder", "build", "eta"])
        self.master.getStatus().subscribe(t4)
        c = interfaces.IControl(self.master)
        req = BuildRequest("forced build for testing", SourceStamp(), 'test_builder')
        c.getBuilder("dummy").requestBuild(req)
        d = req.waitUntilFinished()
        d2 = self.master.botmaster.waitUntilBuilderIdle("dummy")
        dl = defer.DeferredList([d, d2])
        dl.addCallback(self._testSlave_3)
        return dl

    def _testSlave_3(self, res):
        t4 = self.t4
        eta = self.eta
        self.failUnless(eta-1 < t4.eta_build < eta+1, # should be 3 seconds
                        "t4.eta_build was %g, not in (%g,%g)"
                        % (t4.eta_build, eta-1, eta+1))
    

class Client(unittest.TestCase):
    def testAdaptation(self):
        b = builder.BuilderStatus("bname")
        b2 = client.makeRemote(b)
        self.failUnless(isinstance(b2, client.RemoteBuilder))
        b3 = client.makeRemote(None)
        self.failUnless(b3 is None)


class ContactTester(unittest.TestCase):
    def test_notify_invalid_syntax(self):
        irc = MyContact()
        self.assertRaises(words.UsageError, lambda args, who: irc.command_NOTIFY(args, who), "", "mynick")

    def test_notify_list(self):
        irc = MyContact()
        irc.command_NOTIFY("list", "mynick")
        self.failUnlessEqual(irc.message, "The following events are being notified: []", "empty notify list")

        irc.message = ""
        irc.command_NOTIFY("on started", "mynick")
        self.failUnlessEqual(irc.message, "The following events are being notified: ['started']", "on started")

        irc.message = ""
        irc.command_NOTIFY("on finished", "mynick")
        self.failUnlessEqual(irc.message, "The following events are being notified: ['started', 'finished']", "on finished")

        irc.message = ""
        irc.command_NOTIFY("off", "mynick")
        self.failUnlessEqual(irc.message, "The following events are being notified: []", "off all")

        irc.message = ""
        irc.command_NOTIFY("on", "mynick")
        self.failUnlessEqual(irc.message, "The following events are being notified: ['started', 'finished']", "on default set")

        irc.message = ""
        irc.command_NOTIFY("off started", "mynick")
        self.failUnlessEqual(irc.message, "The following events are being notified: ['finished']", "off started")

        irc.message = ""
        irc.command_NOTIFY("on success failure exception", "mynick")
        self.failUnlessEqual(irc.message, "The following events are being notified: ['failure', 'finished', 'exception', 'success']", "on multiple events")

    def test_notification_default(self):
        irc = MyContact()

        my_builder = MyBuilder("builder78")
        my_build = MyIrcBuild(my_builder, 23, builder.SUCCESS)

        irc.buildStarted(my_builder.getName(), my_build)
        self.failUnlessEqual(irc.message, "", "No notification with default settings")

        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, "", "No notification with default settings")

    def test_notification_started(self):
        irc = MyContact()

        my_builder = MyBuilder("builder78")
        my_build = MyIrcBuild(my_builder, 23, builder.SUCCESS)
        my_build.changes = (
            Change(who = 'author1', files = ['file1'], comments = 'comment1', revision = 123),
            Change(who = 'author2', files = ['file2'], comments = 'comment2', revision = 456),
            )

        irc.command_NOTIFY("on started", "mynick")

        irc.message = ""
        irc.buildStarted(my_builder.getName(), my_build)
        self.failUnlessEqual(irc.message, "build #23 of builder78 started including [123, 456]", "Start notification generated with notify_events=['started']")

        irc.message = ""
        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, "", "No finished notification with notify_events=['started']")

    def test_notification_finished(self):
        irc = MyContact()

        my_builder = MyBuilder("builder834")
        my_build = MyIrcBuild(my_builder, 862, builder.SUCCESS)
        my_build.changes = (
            Change(who = 'author1', files = ['file1'], comments = 'comment1', revision = 943),
            )

        irc.command_NOTIFY("on finished", "mynick")

        irc.message = ""
        irc.buildStarted(my_builder.getName(), my_build)
        self.failUnlessEqual(irc.message, "", "No started notification with notify_events=['finished']")

        irc.message = ""
        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, "build #862 of builder834 is complete: Success [step1 step2]  Build details are at http://myserver/mypath?build=765", "Finish notification generated with notify_events=['finished']")

    def test_notification_success(self):
        irc = MyContact()

        my_builder = MyBuilder("builder834")
        my_build = MyIrcBuild(my_builder, 862, builder.SUCCESS)
        my_build.changes = (
            Change(who = 'author1', files = ['file1'], comments = 'comment1', revision = 943),
            )

        irc.command_NOTIFY("on success", "mynick")

        irc.message = ""
        irc.buildStarted(my_builder.getName(), my_build)
        self.failUnlessEqual(irc.message, "", "No started notification with notify_events=['success']")

        irc.message = ""
        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, "build #862 of builder834 is complete: Success [step1 step2]  Build details are at http://myserver/mypath?build=765", "Finish notification generated on success with notify_events=['success']")

        irc.message = ""
        my_build.results = builder.FAILURE
        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, "", "No finish notification generated on failure with notify_events=['success']")

        irc.message = ""
        my_build.results = builder.EXCEPTION
        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, "", "No finish notification generated on exception with notify_events=['success']")

    def test_notification_failed(self):
        irc = MyContact()

        my_builder = MyBuilder("builder834")
        my_build = MyIrcBuild(my_builder, 862, builder.FAILURE)
        my_build.changes = (
            Change(who = 'author1', files = ['file1'], comments = 'comment1', revision = 943),
            )

        irc.command_NOTIFY("on failure", "mynick")

        irc.message = ""
        irc.buildStarted(my_builder.getName(), my_build)
        self.failUnlessEqual(irc.message, "", "No started notification with notify_events=['failed']")

        irc.message = ""
        irc.channel.showBlameList = True
        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, "build #862 of builder834 is complete: Failure [step1 step2]  Build details are at http://myserver/mypath?build=765  blamelist: author1", "Finish notification generated on failure with notify_events=['failed']")
        irc.channel.showBlameList = False

        irc.message = ""
        my_build.results = builder.SUCCESS
        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, "", "No finish notification generated on success with notify_events=['failed']")

        irc.message = ""
        my_build.results = builder.EXCEPTION
        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, "", "No finish notification generated on exception with notify_events=['failed']")

    def test_notification_exception(self):
        irc = MyContact()

        my_builder = MyBuilder("builder834")
        my_build = MyIrcBuild(my_builder, 862, builder.EXCEPTION)
        my_build.changes = (
            Change(who = 'author1', files = ['file1'], comments = 'comment1', revision = 943),
            )

        irc.command_NOTIFY("on exception", "mynick")

        irc.message = ""
        irc.buildStarted(my_builder.getName(), my_build)
        self.failUnlessEqual(irc.message, "", "No started notification with notify_events=['exception']")

        irc.message = ""
        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, "build #862 of builder834 is complete: Exception [step1 step2]  Build details are at http://myserver/mypath?build=765", "Finish notification generated on failure with notify_events=['exception']")

        irc.message = ""
        irc.channel.showBlameList = True
        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, "build #862 of builder834 is complete: Exception [step1 step2]  Build details are at http://myserver/mypath?build=765  blamelist: author1", "Finish notification generated on failure with notify_events=['exception']")
        irc.channel.showBlameList = False

        irc.message = ""
        my_build.results = builder.SUCCESS
        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, "", "No finish notification generated on success with notify_events=['exception']")

        irc.message = ""
        my_build.results = builder.FAILURE
        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, "", "No finish notification generated on exception with notify_events=['exception']")

    def do_x_to_y_notification_test(self, notify, previous_result, new_result, expected_msg):
        irc = MyContact()
        irc.command_NOTIFY("on %s" % notify, "mynick")

        my_builder = MyBuilder("builder834")
        my_build = MyIrcBuild(my_builder, 862, builder.FAILURE)
        my_build.changes = (
            Change(who = 'author1', files = ['file1'], comments = 'comment1', revision = 943),
            )

        previous_build = MyIrcBuild(my_builder, 861, previous_result)
        my_build.setPreviousBuild(previous_build)

        irc.message = ""
        my_build.results = new_result
        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, expected_msg, "Finish notification generated on failure with notify_events=['successToFailure']")

    def test_notification_successToFailure(self):
        self.do_x_to_y_notification_test(notify="successToFailure", previous_result=builder.SUCCESS, new_result=builder.FAILURE,
                                         expected_msg="build #862 of builder834 is complete: Failure [step1 step2]  Build details are at http://myserver/mypath?build=765" )

        self.do_x_to_y_notification_test(notify="successToFailure", previous_result=builder.SUCCESS, new_result=builder.SUCCESS,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="successToFailure", previous_result=builder.SUCCESS, new_result=builder.WARNINGS,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="successToFailure", previous_result=builder.SUCCESS, new_result=builder.EXCEPTION,
                                         expected_msg = "" )

    def test_notification_successToWarnings(self):
        self.do_x_to_y_notification_test(notify="successToWarnings", previous_result=builder.SUCCESS, new_result=builder.WARNINGS,
                                         expected_msg="build #862 of builder834 is complete: Warnings [step1 step2]  Build details are at http://myserver/mypath?build=765" )

        self.do_x_to_y_notification_test(notify="successToWarnings", previous_result=builder.SUCCESS, new_result=builder.SUCCESS,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="successToWarnings", previous_result=builder.SUCCESS, new_result=builder.FAILURE,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="successToWarnings", previous_result=builder.SUCCESS, new_result=builder.EXCEPTION,
                                         expected_msg = "" )

    def test_notification_successToException(self):
        self.do_x_to_y_notification_test(notify="successToException", previous_result=builder.SUCCESS, new_result=builder.EXCEPTION,
                                         expected_msg="build #862 of builder834 is complete: Exception [step1 step2]  Build details are at http://myserver/mypath?build=765" )

        self.do_x_to_y_notification_test(notify="successToException", previous_result=builder.SUCCESS, new_result=builder.SUCCESS,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="successToException", previous_result=builder.SUCCESS, new_result=builder.FAILURE,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="successToException", previous_result=builder.SUCCESS, new_result=builder.WARNINGS,
                                         expected_msg = "" )





    def test_notification_failureToSuccess(self):
        self.do_x_to_y_notification_test(notify="failureToSuccess", previous_result=builder.FAILURE,new_result=builder.SUCCESS,
                                         expected_msg="build #862 of builder834 is complete: Success [step1 step2]  Build details are at http://myserver/mypath?build=765" )

        self.do_x_to_y_notification_test(notify="failureToSuccess", previous_result=builder.FAILURE,new_result=builder.FAILURE,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="failureToSuccess", previous_result=builder.FAILURE,new_result=builder.WARNINGS,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="failureToSuccess", previous_result=builder.FAILURE,new_result=builder.EXCEPTION,
                                         expected_msg = "" )

    def test_notification_failureToWarnings(self):
        self.do_x_to_y_notification_test(notify="failureToWarnings", previous_result=builder.FAILURE, new_result=builder.WARNINGS,
                                         expected_msg="build #862 of builder834 is complete: Warnings [step1 step2]  Build details are at http://myserver/mypath?build=765" )

        self.do_x_to_y_notification_test(notify="failureToWarnings", previous_result=builder.FAILURE, new_result=builder.SUCCESS,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="failureToWarnings", previous_result=builder.FAILURE, new_result=builder.FAILURE,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="failureToWarnings", previous_result=builder.FAILURE, new_result=builder.EXCEPTION,
                                         expected_msg = "" )

    def test_notification_failureToException(self):
        self.do_x_to_y_notification_test(notify="failureToException", previous_result=builder.FAILURE, new_result=builder.EXCEPTION,
                                         expected_msg="build #862 of builder834 is complete: Exception [step1 step2]  Build details are at http://myserver/mypath?build=765" )

        self.do_x_to_y_notification_test(notify="failureToException", previous_result=builder.FAILURE, new_result=builder.SUCCESS,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="failureToException", previous_result=builder.FAILURE, new_result=builder.FAILURE,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="failureToException", previous_result=builder.FAILURE, new_result=builder.WARNINGS,
                                         expected_msg = "" )





    def test_notification_warningsToFailure(self):
        self.do_x_to_y_notification_test(notify="warningsToFailure", previous_result=builder.WARNINGS, new_result=builder.FAILURE,
                                         expected_msg="build #862 of builder834 is complete: Failure [step1 step2]  Build details are at http://myserver/mypath?build=765" )

        self.do_x_to_y_notification_test(notify="warningsToFailure", previous_result=builder.WARNINGS, new_result=builder.SUCCESS,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="warningsToFailure", previous_result=builder.WARNINGS, new_result=builder.WARNINGS,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="warningsToFailure", previous_result=builder.WARNINGS, new_result=builder.EXCEPTION,
                                         expected_msg = "" )

    def test_notification_warningsToSuccess(self):
        self.do_x_to_y_notification_test(notify="warningsToSuccess", previous_result=builder.WARNINGS, new_result=builder.SUCCESS,
                                         expected_msg="build #862 of builder834 is complete: Success [step1 step2]  Build details are at http://myserver/mypath?build=765" )

        self.do_x_to_y_notification_test(notify="warningsToSuccess", previous_result=builder.WARNINGS, new_result=builder.WARNINGS,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="warningsToSuccess", previous_result=builder.WARNINGS, new_result=builder.FAILURE,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="warningsToSuccess", previous_result=builder.WARNINGS, new_result=builder.EXCEPTION,
                                         expected_msg = "" )

    def test_notification_warningsToException(self):
        self.do_x_to_y_notification_test(notify="warningsToException", previous_result=builder.WARNINGS, new_result=builder.EXCEPTION,
                                         expected_msg="build #862 of builder834 is complete: Exception [step1 step2]  Build details are at http://myserver/mypath?build=765" )

        self.do_x_to_y_notification_test(notify="warningsToException", previous_result=builder.WARNINGS, new_result=builder.SUCCESS,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="warningsToException", previous_result=builder.WARNINGS, new_result=builder.FAILURE,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="warningsToException", previous_result=builder.WARNINGS, new_result=builder.WARNINGS,
                                         expected_msg = "" )




    def test_notification_exceptionToFailure(self):
        self.do_x_to_y_notification_test(notify="exceptionToFailure", previous_result=builder.EXCEPTION, new_result=builder.FAILURE,
                                         expected_msg="build #862 of builder834 is complete: Failure [step1 step2]  Build details are at http://myserver/mypath?build=765" )

        self.do_x_to_y_notification_test(notify="exceptionToFailure", previous_result=builder.EXCEPTION, new_result=builder.SUCCESS,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="exceptionToFailure", previous_result=builder.EXCEPTION, new_result=builder.WARNINGS,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="exceptionToFailure", previous_result=builder.EXCEPTION, new_result=builder.EXCEPTION,
                                         expected_msg = "" )

    def test_notification_exceptionToWarnings(self):
        self.do_x_to_y_notification_test(notify="exceptionToWarnings", previous_result=builder.EXCEPTION, new_result=builder.WARNINGS,
                                         expected_msg="build #862 of builder834 is complete: Warnings [step1 step2]  Build details are at http://myserver/mypath?build=765" )

        self.do_x_to_y_notification_test(notify="exceptionToWarnings", previous_result=builder.EXCEPTION, new_result=builder.SUCCESS,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="exceptionToWarnings", previous_result=builder.EXCEPTION, new_result=builder.FAILURE,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="exceptionToWarnings", previous_result=builder.EXCEPTION, new_result=builder.EXCEPTION,
                                         expected_msg = "" )

    def test_notification_exceptionToSuccess(self):
        self.do_x_to_y_notification_test(notify="exceptionToSuccess", previous_result=builder.EXCEPTION, new_result=builder.SUCCESS,
                                         expected_msg="build #862 of builder834 is complete: Success [step1 step2]  Build details are at http://myserver/mypath?build=765" )

        self.do_x_to_y_notification_test(notify="exceptionToSuccess", previous_result=builder.EXCEPTION, new_result=builder.EXCEPTION,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="exceptionToSuccess", previous_result=builder.EXCEPTION, new_result=builder.FAILURE,
                                         expected_msg = "" )

        self.do_x_to_y_notification_test(notify="exceptionToSuccess", previous_result=builder.EXCEPTION, new_result=builder.WARNINGS,
                                         expected_msg = "" )

    def test_notification_set_in_config(self):
        irc = MyContact(channel = MyChannel(notify_events = {'success': 1}))

        my_builder = MyBuilder("builder834")
        my_build = MyIrcBuild(my_builder, 862, builder.SUCCESS)
        my_build.changes = (
            Change(who = 'author1', files = ['file1'], comments = 'comment1', revision = 943),
            )

        irc.message = ""
        irc.buildFinished(my_builder.getName(), my_build, None)
        self.failUnlessEqual(irc.message, "build #862 of builder834 is complete: Success [step1 step2]  Build details are at http://myserver/mypath?build=765", "Finish notification generated on success with notify_events=['success']")

class MyIrcBuild(builder.BuildStatus):
    results = None

    def __init__(self, parent, number, results):
        builder.BuildStatus.__init__(self, parent, number)
        self.results = results
        self.previousBuild = None

    def getResults(self):
        return self.results

    def getText(self):
        return ('step1', 'step2')

    def setPreviousBuild(self, pb):
        self.previousBuild = pb

    def getPreviousBuild(self):
        return self.previousBuild

class URLProducer:
    def getURLForThing(self, build):
        return 'http://myserver/mypath?build=765'

class MyChannel:
    categories = None
    status = URLProducer()
    notify_events = {}

    def __init__(self, notify_events = {}):
        self.notify_events = notify_events
        self.showBlameList = False

class MyContact(words.Contact):
    message = ""

    def __init__(self, channel = MyChannel()):
        words.Contact.__init__(self, channel)
        self.message = ""

    def subscribe_to_build_events(self):
        pass

    def unsubscribe_from_build_events(self):
        pass

    def send(self, msg):
        self.message += msg

class MyIrcStatusBot(words.IrcStatusBot):
    def msg(self, dest, message):
        self.message = ['msg', dest, message]

    def notice(self, dest, message):
        self.message = ['notice', dest, message]

class IrcStatusBotTester(unittest.TestCase):
    def testMsgOrNotice(self):
        channel = MyIrcStatusBot('alice', 'pa55w0od', ['#here'],
                                 builder.SUCCESS, None, {})
        channel.msgOrNotice('bob', 'hello')
        self.failUnlessEqual(channel.message, ['msg', 'bob', 'hello'])

        channel.msgOrNotice('#here', 'hello')
        self.failUnlessEqual(channel.message, ['msg', '#here', 'hello'])

        channel.noticeOnChannel = True

        channel.msgOrNotice('bob', 'hello')
        self.failUnlessEqual(channel.message, ['msg', 'bob', 'hello'])

        channel.msgOrNotice('#here', 'hello')
        self.failUnlessEqual(channel.message, ['notice', '#here', 'hello'])

class StepStatistics(unittest.TestCase):
    def testStepStatistics(self):
        status = builder.BuildStatus(builder.BuilderStatus("test"), 123)
        status.addStepWithName('step1')
        status.addStepWithName('step2')
        status.addStepWithName('step3')
        status.addStepWithName('step4')

        steps = status.getSteps()
        (step1, step2, step3, step4) = steps

        step1.setStatistic('test-prop', 1)
        step3.setStatistic('test-prop', 2)
        step4.setStatistic('test-prop', 4)

        step1.setStatistic('other-prop', 27)
        # Just to have some other properties around

        self.failUnlessEqual(step1.getStatistic('test-prop'), 1,
            'Retrieve an existing property')
        self.failUnlessEqual(step1.getStatistic('test-prop', 99), 1,
            "Don't default an existing property")
        self.failUnlessEqual(step2.getStatistic('test-prop', 99), 99,
            'Default a non-existant property')

        self.failUnlessEqual(
            status.getSummaryStatistic('test-prop', operator.add), 7,
            'Sum property across the build')

        self.failUnlessEqual(
            status.getSummaryStatistic('test-prop', operator.add, 13), 20,
            'Sum property across the build with initial value')

class BuildExpectation(unittest.TestCase):
    class MyBuilderStatus:
        implements(interfaces.IBuilderStatus)

        def setSlavenames(self, slaveName):
            pass

    class MyBuilder(Builder):
        def __init__(self, name):
            Builder.__init__(self, {
                    'name': name,
                    'builddir': '/tmp/somewhere',
                    'slavebuilddir': '/tmp/somewhere_else',
                    'factory': 'aFactory'
                    }, BuildExpectation.MyBuilderStatus())

    class MyBuild(Build):
        def __init__(self, b):
            self.builder = b
            self.remote = None

            step1_progress = progress.StepProgress('step1', ['elapsed'])
            self.progress = progress.BuildProgress([step1_progress])
            step1_progress.setBuildProgress(self.progress)

            step1_progress.start()
            sleep(1);
            step1_progress.finish()

            self.deferred = defer.Deferred()
            self.locks = []
            self.build_status = builder.BuildStatus(b.builder_status, 1)


    def testBuildExpectation_BuildSuccess(self):
        b = BuildExpectation.MyBuilder("builder1")
        build = BuildExpectation.MyBuild(b)

        build.buildFinished(['sometext'], builder.SUCCESS)
        self.failIfEqual(b.expectations.expectedBuildTime(), 0, 'Non-Zero expectation for a failed build')

    def testBuildExpectation_BuildFailure(self):
        b = BuildExpectation.MyBuilder("builder1")
        build = BuildExpectation.MyBuild(b)

        build.buildFinished(['sometext'], builder.FAILURE)
        self.failUnlessEqual(b.expectations, None, 'Zero expectation for a failed build')

class Pruning(unittest.TestCase):
    def runTest(self, files, buildHorizon, logHorizon):
        bstat = builder.BuilderStatus("foo")
        bstat.buildHorizon = buildHorizon
        bstat.logHorizon = logHorizon
        bstat.basedir = "prune-test"

        rmtree(bstat.basedir)
        os.mkdir(bstat.basedir)
        for filename in files:
            open(os.path.join(bstat.basedir, filename), "w").write("TEST")
        bstat.determineNextBuildNumber()

        bstat.prune()

        remaining = os.listdir(bstat.basedir)
        remaining.sort()
        return remaining

    files_base = [
        '10',
        '11',
        '12', '12-log-bar', '12-log-foo',
        '13', '13-log-foo',
        '14', '14-log-bar', '14-log-foo',
    ]

    def test_rmlogs(self):
        remaining = self.runTest(self.files_base, 5, 2)
        self.failUnlessEqual(remaining, [
            '10',
            '11',
            '12',
            '13', '13-log-foo',
            '14', '14-log-bar', '14-log-foo',
        ])

    def test_rmbuilds(self):
        remaining = self.runTest(self.files_base, 2, 0)
        self.failUnlessEqual(remaining, [
            '13', '13-log-foo',
            '14', '14-log-bar', '14-log-foo',
        ])
