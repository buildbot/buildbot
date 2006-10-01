# Here are the tests for the SvnSource

import sys
import time

from twisted.python import log, failure
from twisted.internet import defer
from twisted.trial import unittest

from buildbot.twcompat import maybeWait
from buildbot.changes.changes import Change
from buildbot.changes.svnpoller import SvnSource, split_file_branches

# was changes 1012 in xenomai.org
svn_change_1 = """<?xml version="1.0" encoding="utf-8"?>
<log>
<logentry
   revision="101">
<author>rpm</author>
<date>2006-05-17T14:58:28.494960Z</date>
<paths>
<path
   action="M">/branch/ksrc/arch/i386/hal.c</path>
</paths>
<msg>Remove unused variable</msg>
</logentry>
</log>
"""

svn_change_2 = """<?xml version="1.0" encoding="utf-8"?>
<log>
<logentry
   revision="102">
<author>rpm</author>
<date>2006-05-15T12:54:08.891420Z</date>
<paths>
<path
   action="M">/trunk/ChangeLog</path>
<path
   action="D">/trunk/ksrc/first_file</path>
<path
   action="D">/trunk/ksrc/second_file</path>
</paths>
<msg>Initial Adeos support</msg>
</logentry>
</log>
"""

svn_change_3 = """<?xml version="1.0" encoding="utf-8"?>
<log>
<logentry
   revision="102">
<author>rpm</author>
<date>2006-05-15T12:54:08.891420Z</date>
<paths>
<path
   action="M">/trunk/ChangeLog</path>
<path
   action="D">/trunk/ksrc/first_file</path>
<path
   action="D">/trunk/ksrc/second_file</path>
</paths>
<msg>Upgrade Adeos support</msg>
</logentry>
</log>
"""

def dbgMsg(myString):
    log.msg(myString)
    return 1

class MockSvnSource(SvnSource):
    """Test SvnSource which doesn't actually invoke svn."""
    invocation = 0

    def __init__(self, svnchanges, *args, **kwargs):
        SvnSource.__init__(self, None, *args, **kwargs)
        self.svnchanges = svnchanges

    def _get_changes(self):
        assert self.working
        result = self.svnchanges[self.invocation]
        self.invocation += 1
        #log.msg("MockSvnSource._get_changes %s result %s " % (self.invocation-1, result))
        dbgMsg("MockSvnSource._get_changes %s " % (self.invocation-1))
        return defer.succeed(result)

    def _get_describe(self, dummy, num):
        assert self.working
        dbgMsg("MockSvnSource._get_describe %s " % num)
        return defer.succeed(self.svnchanges[num])

class TestSvnPoller(unittest.TestCase):
    def setUp(self):
        self.changes = []
        self.addChange = self.changes.append

    def failUnlessIn(self, substr, string):
        # this is for compatibility with python2.2
        if isinstance(string, str):
            self.failUnless(string.find(substr) != -1)
        else:
            self.assertIn(substr, string)

    def testCheck(self):
        """successful checks"""
        self.t = MockSvnSource(svnchanges=[ svn_change_1, svn_change_2, svn_change_3],
                              svnuser=None,
                              svnurl='/trunk/',)
        self.t.parent = self

        # The first time, it just learns the change to start at
        self.assert_(self.t.last_change is None)
        self.assert_(not self.t.working)
	dbgMsg("zzz")
        return maybeWait(self.t.checksvn().addCallback(self._testCheck2))

    def _testCheck2(self, res):
	dbgMsg("zzz1")
        self.assertEquals(self.changes, [])
	dbgMsg("zzz2 %s %s" % (self.t.last_change, self.changes))
        self.assertEquals(self.t.last_change, '101')
	dbgMsg("zzz3")

        # Subsequent times, it returns Change objects for new changes.
        return self.t.checksvn().addCallback(self._testCheck3)

    def _testCheck3(self, res):
        # They're supposed to go oldest to newest, so this one must be first.
	tstChange1 = Change(who='rpm',
                   files=['/trunk/ChangeLog',
		          '/trunk/ksrc/first_file',
			  '/trunk/ksrc/second_file'],
                   comments="Initial Adeos support",
                   revision='2',
                   when=self.makeTime("2006/05/15 12:54:08"),
                   branch='trunk').asText()
	dbgMsg("tstChange" + tstChange1)
	dbgMsg("changes[0]" + self.changes[0].asText())

	self.assertEquals(self.changes[0].asText(), tstChange1)
        # Subsequent times, it returns Change objects for new changes.
        return self.t.checksvn().addCallback(self._testCheck4)

    def _testCheck4(self, res):
	dbgMsg("zzz5 %s " % len(self.changes))
        self.assertEquals(len(self.changes), 1)
	dbgMsg("zzz6 %s %s" % (self.t.last_change, self.changes))
        self.assertEquals(self.t.last_change, '102')
	dbgMsg("zzz7")
        self.assert_(not self.t.working)
	tstChange2 = Change(who='rpm',
                   files=['/trunk/ChangeLog',
		          '/trunk/ksrc/first_file',
			  '/trunk/ksrc/second_file'],
                   comments="Initial Adeos support",
                   revision='2',
                   when=self.makeTime("2006/05/15 12:54:08"),
                   branch='trunk').asText()
	dbgMsg("changes[0]" + self.changes[0].asText())
	dbgMsg("tstChange2" + tstChange2)
        self.assertEquals(self.changes[0].asText(), tstChange2)
	dbgMsg(7777)

    def makeTime(self, timestring):
        datefmt = '%Y/%m/%d %H:%M:%S'
        when = time.mktime(time.strptime(timestring, datefmt))
        return when

    def testFailedChanges(self):
        """'svn changes' failure is properly reported"""
        self.t = MockSvnSource(svnchanges=['Subversion client error:\n...'],
                               svnuser=None,
                               svnurl="/trunk")
        self.t.parent = self
        d = self.t.checksvn()
        d.addBoth(self._testFailedChanges2)
        return maybeWait(d)

    def _testFailedChanges2(self, f):
        self.assert_(isinstance(f, failure.Failure))
        self.failUnlessIn('Subversion client error', str(f))
        self.assert_(not self.t.working)

    def testFailedDescribe(self):
        """'svn describe' failure is properly reported"""
        self.t = MockSvnSource(svnchanges=[
	                       svn_change_1,
			       'Subversion client error:\n...',
			       svn_change_2,],
                               svnuser=None)
        self.t.parent = self
        d = self.t.checksvn()
	dbgMsg("xxx")
        d.addCallback(self._testFailedDescribe2)
        return maybeWait(d)

    def _testFailedDescribe2(self, res):
        # first time finds nothing; check again.
	dbgMsg("yy")
        res = self.t.checksvn().addBoth(self._testFailedDescribe3)
        return res

    def _testFailedDescribe3(self, f):
	dbgMsg("yy1 %s" % f)
        self.assert_(isinstance(f, failure.Failure))
	dbgMsg("yy2")
        self.failUnlessIn('Subversion client error', str(f))
	dbgMsg("yy3")
        self.assert_(not self.t.working)
	dbgMsg("yy4")
        self.assertEquals(self.t.last_change, '101')
	dbgMsg("yy5")

    def testAlreadyWorking(self):
        """don't launch a new poll while old is still going"""
        self.t = SvnSource()
        self.t.working = True
        self.assert_(self.t.last_change is None)
        d = self.t.checksvn()
        d.addCallback(self._testAlreadyWorking2)

    def _testAlreadyWorking2(self, res):
        self.assert_(self.t.last_change is None)

# this is the output of "svn info --xml
# svn+ssh://svn.twistedmatrix.com/svn/Twisted/trunk"
prefix_output = """\
<?xml version="1.0"?>
<info>
<entry
   kind="dir"
   path="trunk"
   revision="18354">
<url>svn+ssh://svn.twistedmatrix.com/svn/Twisted/trunk</url>
<repository>
<root>svn+ssh://svn.twistedmatrix.com/svn/Twisted</root>
<uuid>bbbe8e31-12d6-0310-92fd-ac37d47ddeeb</uuid>
</repository>
<commit
   revision="18352">
<author>jml</author>
<date>2006-10-01T02:37:34.063255Z</date>
</commit>
</entry>
</info>
"""

# and this is "svn info --xml svn://svn.twistedmatrix.com/svn/Twisted". I
# think this is kind of a degenerate case.. it might even be a form of error.
prefix_output_2 = """\
<?xml version="1.0"?>
<info>
</info>
"""

# this is the svn info output for a local repository, svn info --xml
# file:///home/warner/stuff/Projects/BuildBot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository
prefix_output_3 = """\
<?xml version="1.0"?>
<info>
<entry
   kind="dir"
   path="SVN-Repository"
   revision="3">
<url>file:///home/warner/stuff/Projects/BuildBot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository</url>
<repository>
<root>file:///home/warner/stuff/Projects/BuildBot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository</root>
<uuid>c0f47ff4-ba1e-0410-96b5-d44cc5c79e7f</uuid>
</repository>
<commit
   revision="3">
<author>warner</author>
<date>2006-10-01T07:37:04.182499Z</date>
</commit>
</entry>
</info>
"""

# % svn info --xml file:///home/warner/stuff/Projects/BuildBot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository/sample/trunk

prefix_output_4 = """\
<?xml version="1.0"?>
<info>
<entry
   kind="dir"
   path="trunk"
   revision="3">
<url>file:///home/warner/stuff/Projects/BuildBot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository/sample/trunk</url>
<repository>
<root>file:///home/warner/stuff/Projects/BuildBot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository</root>
<uuid>c0f47ff4-ba1e-0410-96b5-d44cc5c79e7f</uuid>
</repository>
<commit
   revision="1">
<author>warner</author>
<date>2006-10-01T07:37:02.286440Z</date>
</commit>
</entry>
</info>
"""



class ComputePrefix(unittest.TestCase):
    def test1(self):
        base = "svn+ssh://svn.twistedmatrix.com/svn/Twisted/trunk"
        s = SvnSource(base + "/")
        self.failUnlessEqual(s.svnurl, base) # certify slash-stripping
        prefix = s._determine_prefix_2(prefix_output)
        self.failUnlessEqual(prefix, "trunk")
        self.failUnlessEqual(s._prefix, prefix)

    def test2(self):
        base = "svn+ssh://svn.twistedmatrix.com/svn/Twisted"
        s = SvnSource(base)
        self.failUnlessEqual(s.svnurl, base)
        prefix = s._determine_prefix_2(prefix_output_2)
        self.failUnlessEqual(prefix, "")

    def test3(self):
        base = "file:///home/warner/stuff/Projects/BuildBot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository"
        s = SvnSource(base)
        self.failUnlessEqual(s.svnurl, base)
        prefix = s._determine_prefix_2(prefix_output_3)
        self.failUnlessEqual(prefix, "")

    def test4(self):
        base = "file:///home/warner/stuff/Projects/BuildBot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository/sample/trunk"
        s = SvnSource(base)
        self.failUnlessEqual(s.svnurl, base)
        prefix = s._determine_prefix_2(prefix_output_4)
        self.failUnlessEqual(prefix, "sample/trunk")

# output from svn log on .../SVN-Repository/sample
# (so it includes trunk and branches)
changes_output_1 = """\
<?xml version="1.0"?>
<log>
<logentry
   revision="3">
<author>warner</author>
<date>2006-10-01T07:37:04.182499Z</date>
<paths>
<path
   action="M">/sample/branch/main.c</path>
</paths>
<msg>commit_on_branch</msg>
</logentry>
<logentry
   revision="2">
<author>warner</author>
<date>2006-10-01T07:37:03.175326Z</date>
<paths>
<path
   copyfrom-path="/sample/trunk"
   copyfrom-rev="1"
   action="A">/sample/branch</path>
</paths>
<msg>make_branch</msg>
</logentry>
</log>
"""

class ComputeChanges(unittest.TestCase):
    def test1(self):
        base = "file:///home/warner/stuff/Projects/BuildBot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository/sample"
        s = SvnSource(base)
        s._prefix = "sample"
        doc = s._parse_logs(changes_output_1)

        newlast, logentries = s._filter_new_logentries(doc, 3)
        self.failUnlessEqual(newlast, 3)
        self.failUnlessEqual(len(logentries), 0)

        newlast, logentries = s._filter_new_logentries(doc, 2)
        self.failUnlessEqual(newlast, 3)
        self.failUnlessEqual(len(logentries), 1)

        newlast, logentries = s._filter_new_logentries(doc, 0)
        self.failUnlessEqual(newlast, 3)
        self.failUnlessEqual(len(logentries), 2)

    def split_file(self, path):
        pieces = path.split("/")
        if pieces[0] == "branch":
            return "branch", "/".join(pieces[1:])
        if pieces[0] == "trunk":
            return None, "/".join(pieces[1:])
        raise RuntimeError("there shouldn't be any files like %s" % path)

    def testChanges(self):
        base = "file:///home/warner/stuff/Projects/BuildBot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository/sample"
        s = SvnSource(base, split_file=self.split_file)
        s._prefix = "sample"
        doc = s._parse_logs(changes_output_1)
        newlast, logentries = s._filter_new_logentries(doc, 0)
        changes = s._create_changes(logentries)
        self.failUnlessEqual(len(changes), 2)
        self.failUnlessEqual(changes[0].branch, "branch")
        self.failUnlessEqual(changes[1].branch, "branch")
        self.failUnlessEqual(changes[1].files, ["main.c"])
