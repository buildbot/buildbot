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

import os
import xml.dom.minidom
from twisted.internet import defer
from twisted.trial import unittest
from buildbot.test.util import changesource, gpo, compat
from buildbot.changes import svnpoller

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



# output from svn log on .../SVN-Repository/sample
# (so it includes trunk and branches)
sample_base = ("file:///usr/home/warner/stuff/Projects/BuildBot/trees/misc/" +
               "_trial_temp/test_vc/repositories/SVN-Repository/sample")
sample_logentries = [None] * 6

sample_logentries[5] = """\
<logentry
   revision="6">
<author>warner</author>
<date>2006-10-01T19:35:16.165664Z</date>
<paths>
<path
   action="D">/sample/branch/version.c</path>
</paths>
<msg>revised_to_2</msg>
</logentry>
"""

sample_logentries[4] = """\
<logentry
   revision="5">
<author>warner</author>
<date>2006-10-01T19:35:16.165664Z</date>
<paths>
<path
   action="D">/sample/branch</path>
</paths>
<msg>revised_to_2</msg>
</logentry>
"""

sample_logentries[3] = """\
<logentry
   revision="4">
<author>warner</author>
<date>2006-10-01T19:35:16.165664Z</date>
<paths>
<path
   action="M">/sample/trunk/version.c</path>
</paths>
<msg>revised_to_2</msg>
</logentry>
"""

sample_logentries[2] = """\
<logentry
   revision="3">
<author>warner</author>
<date>2006-10-01T19:35:10.215692Z</date>
<paths>
<path
   action="M">/sample/branch/main.c</path>
</paths>
<msg>commit_on_branch</msg>
</logentry>
"""

sample_logentries[1] = """\
<logentry
   revision="2">
<author>warner</author>
<date>2006-10-01T19:35:09.154973Z</date>
<paths>
<path
   copyfrom-path="/sample/trunk"
   copyfrom-rev="1"
   action="A">/sample/branch</path>
</paths>
<msg>make_branch</msg>
</logentry>
"""

sample_logentries[0] = """\
<logentry
   revision="1">
<author>warner</author>
<date>2006-10-01T19:35:08.642045Z</date>
<paths>
<path
   action="A">/sample</path>
<path
   action="A">/sample/trunk</path>
<path
   action="A">/sample/trunk/subdir/subdir.c</path>
<path
   action="A">/sample/trunk/main.c</path>
<path
   action="A">/sample/trunk/version.c</path>
<path
   action="A">/sample/trunk/subdir</path>
</paths>
<msg>sample_project_files</msg>
</logentry>
"""

sample_info_output = """\
<?xml version="1.0"?>
<info>
<entry
   kind="dir"
   path="sample"
   revision="4">
<url>file:///usr/home/warner/stuff/Projects/BuildBot/trees/misc/_trial_temp/test_vc/repositories/SVN-Repository/sample</url>
<repository>
<root>file:///usr/home/warner/stuff/Projects/BuildBot/trees/misc/_trial_temp/test_vc/repositories/SVN-Repository</root>
<uuid>4f94adfc-c41e-0410-92d5-fbf86b7c7689</uuid>
</repository>
<commit
   revision="4">
<author>warner</author>
<date>2006-10-01T19:35:16.165664Z</date>
</commit>
</entry>
</info>
"""


changes_output_template = """\
<?xml version="1.0"?>
<log>
%s</log>
"""

def make_changes_output(maxrevision):
    # return what 'svn log' would have just after the given revision was
    # committed
    logs = sample_logentries[0:maxrevision]
    assert len(logs) == maxrevision
    logs.reverse()
    output = changes_output_template % ("".join(logs))
    return output

def make_logentry_elements(maxrevision):
    "return the corresponding logentry elements for the given revisions"
    doc = xml.dom.minidom.parseString(make_changes_output(maxrevision))
    return doc.getElementsByTagName("logentry")

def split_file(path):
    pieces = path.split("/")
    if pieces[0] == "branch":
        return "branch", "/".join(pieces[1:])
    if pieces[0] == "trunk":
        return None, "/".join(pieces[1:])
    raise RuntimeError("there shouldn't be any files like %r" % path)


class TestSVNPoller(gpo.GetProcessOutputMixin,
                    changesource.ChangeSourceMixin,
                    unittest.TestCase):

    def setUp(self):
        self.setUpGetProcessOutput()
        return self.setUpChangeSource()

    def tearDown(self):
        self.tearDownGetProcessOutput()
        return self.tearDownChangeSource()

    def attachSVNPoller(self, *args, **kwargs):
        s = svnpoller.SVNPoller(*args, **kwargs)
        self.attachChangeSource(s)
        return s

    def add_svn_command_result(self, command, result):
        self.addGetProcessOutputResult(
                self.gpoSubcommandPattern('svn', command),
                result)


    # tests

    def test_describe(self):
        s = self.attachSVNPoller('file://')
        self.assertSubstring("SVNPoller", s.describe())

    def test_strip_svnurl(self):
        base = "svn+ssh://svn.twistedmatrix.com/svn/Twisted/trunk"
        s = self.attachSVNPoller(base + "/")
        self.failUnlessEqual(s.svnurl, base)

    def do_test_get_prefix(self, base, output, expected):
        s = self.attachSVNPoller(base)
        self.add_svn_command_result('info', output)
        d = s.get_prefix()
        def check(prefix):
            self.failUnlessEqual(prefix, expected)
        d.addCallback(check)
        return d

    def test_get_prefix_1(self):
        base = "svn+ssh://svn.twistedmatrix.com/svn/Twisted/trunk"
        return self.do_test_get_prefix(base, prefix_output, 'trunk')

    def test_get_prefix_2(self):
        base = "svn+ssh://svn.twistedmatrix.com/svn/Twisted"
        return self.do_test_get_prefix(base, prefix_output_2, '')

    def test_get_prefix_3(self):
        base = ("file:///home/warner/stuff/Projects/BuildBot/trees/" +
                "svnpoller/_trial_temp/test_vc/repositories/SVN-Repository")
        return self.do_test_get_prefix(base, prefix_output_3, '')

    def test_get_prefix_4(self):
        base = ("file:///home/warner/stuff/Projects/BuildBot/trees/" +
                "svnpoller/_trial_temp/test_vc/repositories/SVN-Repository/sample/trunk")
        return self.do_test_get_prefix(base, prefix_output_3, 'sample/trunk')

    def test_log_parsing(self):
        s = self.attachSVNPoller('file:///foo')
        output = make_changes_output(4)
        entries = s.parse_logs(output)
        # no need for elaborate assertions here; this is minidom's logic
        self.assertEqual(len(entries), 4)

    def test_get_new_logentries(self):
        s = self.attachSVNPoller('file:///foo')
        entries = make_logentry_elements(4)

        s.last_change = 4
        new = s.get_new_logentries(entries)
        self.assertEqual(s.last_change, 4)
        self.assertEqual(len(new), 0)

        s.last_change = 3
        new = s.get_new_logentries(entries)
        self.assertEqual(s.last_change, 4)
        self.assertEqual(len(new), 1)

        s.last_change = 1
        new = s.get_new_logentries(entries)
        self.assertEqual(s.last_change, 4)
        self.assertEqual(len(new), 3)

        # special case: if last_change is None, then no new changes are queued
        s.last_change = None
        new = s.get_new_logentries(entries)
        self.assertEqual(s.last_change, 4)
        self.assertEqual(len(new), 0)

    def test_create_changes(self):
        base = ("file:///home/warner/stuff/Projects/BuildBot/trees/" +
                "svnpoller/_trial_temp/test_vc/repositories/SVN-Repository/sample")
        s = self.attachSVNPoller(base, split_file=split_file)
        s._prefix = "sample"

        logentries = dict(zip(xrange(1, 7), reversed(make_logentry_elements(6))))
        changes = s.create_changes(reversed([ logentries[3], logentries[2] ]))
        self.failUnlessEqual(len(changes), 2)
        # note that parsing occurs in reverse
        self.failUnlessEqual(changes[0]['branch'], "branch")
        self.failUnlessEqual(changes[0]['revision'], '2')
        self.failUnlessEqual(changes[1]['branch'], "branch")
        self.failUnlessEqual(changes[1]['files'], ["main.c"])
        self.failUnlessEqual(changes[1]['revision'], '3')

        changes = s.create_changes([ logentries[4] ])
        self.failUnlessEqual(len(changes), 1)
        self.failUnlessEqual(changes[0]['branch'], None)
        self.failUnlessEqual(changes[0]['revision'], '4')
        self.failUnlessEqual(changes[0]['files'], ["version.c"])

        # r5 should *not* create a change as it's a branch deletion
        changes = s.create_changes([ logentries[5] ])
        self.failUnlessEqual(len(changes), 0)

        # r6 should create a change as it's not deleting an entire branch
        changes = s.create_changes([ logentries[6] ])
        self.failUnlessEqual(len(changes), 1)
        self.failUnlessEqual(changes[0]['branch'], 'branch')
        self.failUnlessEqual(changes[0]['revision'], '6')
        self.failUnlessEqual(changes[0]['files'], ["version.c"])

    def test_poll(self):
        s = self.attachSVNPoller(sample_base, split_file=split_file,
                svnuser='dustin', svnpasswd='bbrocks')

        d = defer.succeed(None)

        # fire it the first time; it should do nothing
        def setup_first(_):
            self.add_svn_command_result('info', sample_info_output) # for get_root
            self.add_svn_command_result('log', make_changes_output(1))
        d.addCallback(setup_first)
        d.addCallback(lambda _ : s.poll())
        def check_first(_):
            # no changes generated on the first iteration
            self.assertEqual(self.changes_added, [])
            self.failUnlessEqual(s.last_change, 1)
        d.addCallback(check_first)

        # now fire it again, nothing changing
        def setup_second(_):
            self.add_svn_command_result('log', make_changes_output(1))
        d.addCallback(setup_second)
        d.addCallback(lambda _ : s.poll())
        def check_second(_):
            self.assertEqual(self.changes_added, [])
            self.failUnlessEqual(s.last_change, 1)
        d.addCallback(check_second)

        # and again, with r2 this time
        def setup_third(_):
            self.add_svn_command_result('log', make_changes_output(2))
        d.addCallback(setup_third)
        d.addCallback(lambda _ : s.poll())
        def check_third(_):
            self.assertEqual(len(self.changes_added), 1)
            c = self.changes_added[0]
            self.failUnlessEqual(c['branch'], "branch")
            self.failUnlessEqual(c['revision'], '2')
            self.failUnlessEqual(c['files'], ['']) # signals a new branch
            self.failUnlessEqual(c['comments'], "make_branch")
            self.failUnlessEqual(s.last_change, 2)
        d.addCallback(check_third)

        # and again with both r3 and r4 appearing together
        def setup_fourth(_):
            self.changes_added = []
            self.add_svn_command_result('log', make_changes_output(4))
        d.addCallback(setup_fourth)
        d.addCallback(lambda _ : s.poll())
        def check_fourth(_):
            self.assertEqual(len(self.changes_added), 2)
            c = self.changes_added[0]
            self.failUnlessEqual(c['branch'], "branch")
            self.failUnlessEqual(c['revision'], '3')
            self.failUnlessEqual(c['files'], ["main.c"])
            self.failUnlessEqual(c['comments'], "commit_on_branch")
            c = self.changes_added[1]
            self.failUnlessEqual(c['branch'], None)
            self.failUnlessEqual(c['revision'], '4')
            self.failUnlessEqual(c['files'], ["version.c"])
            self.failUnlessEqual(c['comments'], "revised_to_2")
            self.failUnlessEqual(s.last_change, 4)
        d.addCallback(check_fourth)

        return d

    def test_cachepath_empty(self):
        cachepath = os.path.abspath('revcache')
        if os.path.exists(cachepath):
            os.unlink(cachepath)
        s = self.attachSVNPoller(sample_base, cachepath=cachepath)
        self.assertEqual(s.last_change, None)

    def test_cachepath_full(self):
        cachepath = os.path.abspath('revcache')
        open(cachepath, "w").write('33')
        s = self.attachSVNPoller(sample_base, cachepath=cachepath)
        self.assertEqual(s.last_change, 33)

        s.last_change = 44
        s.finished_ok(None)
        self.assertEqual(open(cachepath).read().strip(), '44')

    @compat.usesFlushLoggedErrors
    def test_cachepath_bogus(self):
        cachepath = os.path.abspath('revcache')
        open(cachepath, "w").write('nine')
        s = self.attachSVNPoller(sample_base, cachepath=cachepath)
        self.assertEqual(s.last_change, None)
        self.assertEqual(s.cachepath, None)
        # it should have called log.err once with a ValueError
        self.assertEqual(len(self.flushLoggedErrors(ValueError)), 1)

    def test_constructor_pollinterval(self):
        self.attachSVNPoller(sample_base, pollinterval=100) # just don't fail!

class TestSplitFile(unittest.TestCase):
    def test_split_file_alwaystrunk(self):
        self.assertEqual(svnpoller.split_file_alwaystrunk('foo'), (None, 'foo'))

    def test_split_file_branches(self):
        self.assertEqual(
                svnpoller.split_file_branches('trunk/subdir/file.c'),
                (None, 'subdir/file.c'))
        self.assertEqual(
                svnpoller.split_file_branches('branches/1.5.x/subdir/file.c'),
                ('branches/1.5.x', 'subdir/file.c'))
        # tags are ignored:
        self.assertEqual(
                svnpoller.split_file_branches('tags/testthis/subdir/file.c'),
                None)
