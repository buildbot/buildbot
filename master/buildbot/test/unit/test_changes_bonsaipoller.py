# This file is part of Buildbot.  Buildbot is free software: you can
# redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, version 2.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 51
# Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#
# Copyright Buildbot Team Members

from copy import deepcopy
import re

from twisted.trial import unittest
from twisted.internet import defer
from twisted.web import client
from buildbot.test.util import changesource
from buildbot.util import epoch2datetime
from buildbot.changes.bonsaipoller import FileNode, CiNode, BonsaiResult, \
     BonsaiParser, BonsaiPoller, InvalidResultError, EmptyResult

log1 = "Add Bug 338541a"
who1 = "sar@gmail.com"
date1 = 1161908700
log2 = "bug 357427 add static ctor/dtor methods"
who2 = "aarrg@ooacm.org"
date2 = 1161910620
log3 = "Testing log #3 lbah blah"
who3 = "huoents@hueont.net"
date3 = 1089822728
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

class TestBonsaiParser(unittest.TestCase):
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

class TestBonsaiPoller(changesource.ChangeSourceMixin, unittest.TestCase):
    def setUp(self):
        d = self.setUpChangeSource()
        def create_poller(_):
            self.attachChangeSource(BonsaiPoller('http://bonsai.mozilla.org',
                                       'all', 'seamonkey'))
        d.addCallback(create_poller)
        return d

    def tearDown(self):
        return self.tearDownChangeSource()

    def fakeGetPage(self, result):
        """Install a fake getPage that puts the requested URL in C{self.getPage_got_url}
        and return C{result}"""
        self.getPage_got_url = None
        def fake(url, timeout=None):
            self.getPage_got_url = url
            return defer.succeed(result)
        self.patch(client, "getPage", fake)

    # tests

    def test_describe(self):
        assert re.search(r'bonsai\.mozilla\.org', self.changesource.describe())

    def test_poll_bad(self):
        # Make sure a change is not submitted if the BonsaiParser fails, and
        # that the poll operation catches the exception correctly
        self.fakeGetPage(badUnparsedResult)
        d = self.changesource.poll()
        def check(_):
            self.assertEqual(len(self.changes_added), 0)
        d.addCallback(check)
        return d

    def test_poll_good(self):
        self.fakeGetPage(goodUnparsedResult)
        d = self.changesource.poll()
        def check(_):
            self.assertEqual(len(self.changes_added), 3)
            self.assertEqual(self.changes_added[0]['author'], who1)
            self.assertEqual(self.changes_added[0]['when_timestamp'],
                                            epoch2datetime(date1))
            self.assertEqual(self.changes_added[0]['comments'], log1)
            self.assertEqual(self.changes_added[0]['branch'], 'seamonkey')
            self.assertEqual(self.changes_added[0]['files'],
                    [ '%s (revision %s)' % (file1, rev1) ])
            self.assertEqual(self.changes_added[1]['author'], who2)
            self.assertEqual(self.changes_added[1]['when_timestamp'],
                                            epoch2datetime(date2))
            self.assertEqual(self.changes_added[1]['comments'], log2)
            self.assertEqual(self.changes_added[1]['files'],
                    [ '%s (revision %s)' % (file2, rev2),
                      '%s (revision %s)' % (file3, rev3) ])
            self.assertEqual(self.changes_added[2]['author'], who3)
            self.assertEqual(self.changes_added[2]['comments'], log3)
            self.assertEqual(self.changes_added[2]['when_timestamp'],
                                            epoch2datetime(date3))
            self.assertEqual(self.changes_added[2]['files'], [])
        d.addCallback(check)
        return d
