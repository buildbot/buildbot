# -*- test-case-name: buildbot.test.test_bonsaipoller -*-

from twisted.trial import unittest
from buildbot.changes.bonsaipoller import FileNode, CiNode, BonsaiResult, \
     BonsaiParser, BonsaiPoller, InvalidResultError, EmptyResult
from buildbot.changes.changes import ChangeMaster

from copy import deepcopy
import re

log1 = "Add Bug 338541a"
who1 = "sar@gmail.com"
date1 = 1161908700
log2 = "bug 357427 add static ctor/dtor methods"
who2 = "aarrg@ooacm.org"
date2 = 1161910620
log3 = "Testing log #3 lbah blah"
who3 = "huoents@hueont.net"
date3 = 1889822728
rev1 = "1.8"
file1 = "mozilla/testing/mochitest/tests/index.html"
rev2 = "1.1"
file2 = "mozilla/testing/mochitest/tests/test_bug338541.xhtml"
rev3 = "1.1812"
file3 = "mozilla/xpcom/threads/nsAutoLock.cpp"
rev4 = "1.3"
file4 = "mozilla/xpcom/threads/nsAutoLock.h"
rev5 = "2.4"
file5 = "mozilla/xpcom/threads/test.cpp"

nodes = []
files = []
files.append(FileNode(rev1,file1))
nodes.append(CiNode(log1, who1, date1, files))

files = []
files.append(FileNode(rev2, file2))
files.append(FileNode(rev3, file3))
nodes.append(CiNode(log2, who2, date2, files))

nodes.append(CiNode(log3, who3, date3, []))

goodParsedResult = BonsaiResult(nodes)

goodUnparsedResult = """\
<?xml version="1.0"?>
<queryResults>
<ci who="%s" date="%d">
  <log>%s</log>
  <files>
    <f rev="%s">%s</f>
  </files>
</ci>
<ci who="%s" date="%d">
  <log>%s</log>
  <files>
    <f rev="%s">%s</f>
    <f rev="%s">%s</f>
  </files>
</ci>
<ci who="%s" date="%d">
  <log>%s</log>
  <files>
  </files>
</ci>
</queryResults>
""" % (who1, date1, log1, rev1, file1,
       who2, date2, log2, rev2, file2, rev3, file3,
       who3, date3, log3)

badUnparsedResult = deepcopy(goodUnparsedResult)
badUnparsedResult = badUnparsedResult.replace("</queryResults>", "")

invalidDateResult = deepcopy(goodUnparsedResult)
invalidDateResult = invalidDateResult.replace(str(date1), "foobar")

missingFilenameResult = deepcopy(goodUnparsedResult)
missingFilenameResult = missingFilenameResult.replace(file2, "")

duplicateLogResult = deepcopy(goodUnparsedResult)
duplicateLogResult = re.sub("<log>"+log1+"</log>",
                            "<log>blah</log><log>blah</log>",
                            duplicateLogResult)

duplicateFilesResult = deepcopy(goodUnparsedResult)
duplicateFilesResult = re.sub("<files>\s*</files>",
                              "<files></files><files></files>",
                              duplicateFilesResult)

missingCiResult = deepcopy(goodUnparsedResult)
r = re.compile("<ci.*</ci>", re.DOTALL | re.MULTILINE)
missingCiResult = re.sub(r, "", missingCiResult)

badResultMsgs = { 'badUnparsedResult':
    "BonsaiParser did not raise an exception when given a bad query",
                  'invalidDateResult':
    "BonsaiParser did not raise an exception when given an invalid date",
                  'missingRevisionResult':
    "BonsaiParser did not raise an exception when a revision was missing",
                  'missingFilenameResult':
    "BonsaiParser did not raise an exception when a filename was missing",
                  'duplicateLogResult':
    "BonsaiParser did not raise an exception when there was two <log> tags",
                  'duplicateFilesResult':
    "BonsaiParser did not raise an exception when there was two <files> tags",
                  'missingCiResult':
    "BonsaiParser did not raise an exception when there was no <ci> tags"
}

noCheckinMsgResult = """\
<?xml version="1.0"?>
<queryResults>
<ci who="johndoe@domain.tld" date="12345678">
 <log></log>
 <files>
  <f rev="1.1">first/file.ext</f>
 </files>
</ci>
<ci who="johndoe@domain.tld" date="12345678">
 <log></log>
 <files>
  <f rev="1.2">second/file.ext</f>
 </files>
</ci>
<ci who="johndoe@domain.tld" date="12345678">
 <log></log>
 <files>
  <f rev="1.3">third/file.ext</f>
 </files>
</ci>
</queryResults>
"""

noCheckinMsgRef = [dict(filename="first/file.ext",
                     revision="1.1"),
                dict(filename="second/file.ext",
                     revision="1.2"),
                dict(filename="third/file.ext",
                     revision="1.3")]

class FakeChangeMaster(ChangeMaster):
    def __init__(self):
        ChangeMaster.__init__(self)

    def addChange(self, change):
        pass

class FakeBonsaiPoller(BonsaiPoller):
    def __init__(self):
        BonsaiPoller.__init__(self, "fake url", "fake module", "fake branch")
        self.parent = FakeChangeMaster()

class TestBonsaiPoller(unittest.TestCase):
    def testFullyFormedResult(self):
        br = BonsaiParser(goodUnparsedResult)
        result = br.getData()
        # make sure the result is a BonsaiResult
        self.failUnless(isinstance(result, BonsaiResult))
        # test for successful parsing
        self.failUnlessEqual(goodParsedResult, result,
            "BonsaiParser did not return the expected BonsaiResult")

    def testBadUnparsedResult(self):
        try:
            BonsaiParser(badUnparsedResult)
            self.fail(badResultMsgs["badUnparsedResult"])
        except InvalidResultError:
            pass

    def testInvalidDateResult(self):
        try:
            BonsaiParser(invalidDateResult)
            self.fail(badResultMsgs["invalidDateResult"])
        except InvalidResultError:
            pass

    def testMissingFilenameResult(self):
        try:
            BonsaiParser(missingFilenameResult)
            self.fail(badResultMsgs["missingFilenameResult"])
        except InvalidResultError:
            pass

    def testDuplicateLogResult(self):
        try:
            BonsaiParser(duplicateLogResult)
            self.fail(badResultMsgs["duplicateLogResult"])
        except InvalidResultError:
            pass

    def testDuplicateFilesResult(self):
        try:
            BonsaiParser(duplicateFilesResult)
            self.fail(badResultMsgs["duplicateFilesResult"])
        except InvalidResultError:
            pass

    def testMissingCiResult(self):
        try:
            BonsaiParser(missingCiResult)
            self.fail(badResultMsgs["missingCiResult"])
        except EmptyResult:
            pass

    def testChangeNotSubmitted(self):
        "Make sure a change is not submitted if the BonsaiParser fails"
        poller = FakeBonsaiPoller()
        lastChangeBefore = poller.lastChange
        poller._process_changes(badUnparsedResult)
        # self.lastChange will not be updated if the change was not submitted
        self.failUnlessEqual(lastChangeBefore, poller.lastChange)

    def testParserWorksAfterInvalidResult(self):
        """Make sure the BonsaiPoller still works after catching an
        InvalidResultError"""

        poller = FakeBonsaiPoller()

        lastChangeBefore = poller.lastChange
        # generate an exception first. pretend that we're doing a poll and
        # increment the timestamp, otherwise the failIfEqual test at the
        # bottom will depend upon there being a noticeable difference between
        # two successive calls to time.time().
        poller.lastPoll += 1.0
        poller._process_changes(badUnparsedResult)
        # now give it a valid one...
        poller.lastPoll += 1.0
        poller._process_changes(goodUnparsedResult)
        # if poller.lastChange has not been updated then the good result
        # was not parsed
        self.failIfEqual(lastChangeBefore, poller.lastChange)

    def testMergeEmptyLogMsg(self):
        """Ensure that BonsaiPoller works around the bonsai xml output
        issue when the check-in comment is empty"""
        bp = BonsaiParser(noCheckinMsgResult)
        result = bp.getData()
        self.failUnlessEqual(len(result.nodes), 1)
        self.failUnlessEqual(result.nodes[0].who, "johndoe@domain.tld")
        self.failUnlessEqual(result.nodes[0].date, 12345678)
        self.failUnlessEqual(result.nodes[0].log, "")
        for file, ref in zip(result.nodes[0].files, noCheckinMsgRef):
            self.failUnlessEqual(file.filename, ref['filename'])
            self.failUnlessEqual(file.revision, ref['revision'])
