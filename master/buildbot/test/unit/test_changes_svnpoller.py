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

from __future__ import absolute_import
from __future__ import print_function

import os
import xml.dom.minidom

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.changes import svnpoller
from buildbot.test.util import changesource
from buildbot.test.util import gpo

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
# file:///home/warner/stuff/Projects/Buildbot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository
prefix_output_3 = """\
<?xml version="1.0"?>
<info>
<entry
   kind="dir"
   path="SVN-Repository"
   revision="3">
<url>file:///home/warner/stuff/Projects/Buildbot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository</url>
<repository>
<root>file:///home/warner/stuff/Projects/Buildbot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository</root>
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

# % svn info --xml file:///home/warner/stuff/Projects/Buildbot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository/sample/trunk

prefix_output_4 = """\
<?xml version="1.0"?>
<info>
<entry
   kind="dir"
   path="trunk"
   revision="3">
<url>file:///home/warner/stuff/Projects/Buildbot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository/sample/trunk</url>
<repository>
<root>file:///home/warner/stuff/Projects/Buildbot/trees/svnpoller/_trial_temp/test_vc/repositories/SVN-Repository</root>
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
sample_base = ("file:///usr/home/warner/stuff/Projects/Buildbot/trees/misc/" +
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
<url>file:///usr/home/warner/stuff/Projects/Buildbot/trees/misc/_trial_temp/test_vc/repositories/SVN-Repository/sample</url>
<repository>
<root>file:///usr/home/warner/stuff/Projects/Buildbot/trees/misc/_trial_temp/test_vc/repositories/SVN-Repository</root>
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
        return dict(branch="branch", path="/".join(pieces[1:]))
    if pieces[0] == "trunk":
        return dict(path="/".join(pieces[1:]))
    raise RuntimeError("there shouldn't be any files like %r" % path)


class TestSVNPoller(gpo.GetProcessOutputMixin,
                    changesource.ChangeSourceMixin,
                    unittest.TestCase):

    def setUp(self):
        self.setUpGetProcessOutput()
        return self.setUpChangeSource()

    def tearDown(self):
        return self.tearDownChangeSource()

    def attachSVNPoller(self, *args, **kwargs):
        s = svnpoller.SVNPoller(*args, **kwargs)
        self.attachChangeSource(s)
        return s

    def add_svn_command_result(self, command, result):
        self.expectCommands(
            gpo.Expect('svn', command).stdout(result))

    # tests
    def test_describe(self):
        s = self.attachSVNPoller('file://')
        self.assertSubstring("SVNPoller", s.describe())

    def test_name(self):
        s = self.attachSVNPoller('file://')
        self.assertEqual("file://", s.name)

        s = self.attachSVNPoller('file://', name='MyName')
        self.assertEqual("MyName", s.name)

    def test_strip_repourl(self):
        base = "svn+ssh://svn.twistedmatrix.com/svn/Twisted/trunk"
        s = self.attachSVNPoller(base + "/")
        self.assertEqual(s.repourl, base)

    def do_test_get_prefix(self, base, output, expected):
        s = self.attachSVNPoller(base)
        self.expectCommands(
            gpo.Expect('svn', 'info', '--xml', '--non-interactive', base).stdout(output))
        d = s.get_prefix()

        def check(prefix):
            self.assertEqual(prefix, expected)
            self.assertAllCommandsRan()
        d.addCallback(check)
        return d

    def test_get_prefix_1(self):
        base = "svn+ssh://svn.twistedmatrix.com/svn/Twisted/trunk"
        return self.do_test_get_prefix(base, prefix_output, 'trunk')

    def test_get_prefix_2(self):
        base = "svn+ssh://svn.twistedmatrix.com/svn/Twisted"
        return self.do_test_get_prefix(base, prefix_output_2, '')

    def test_get_prefix_3(self):
        base = ("file:///home/warner/stuff/Projects/Buildbot/trees/" +
                "svnpoller/_trial_temp/test_vc/repositories/SVN-Repository")
        return self.do_test_get_prefix(base, prefix_output_3, '')

    def test_get_prefix_4(self):
        base = ("file:///home/warner/stuff/Projects/Buildbot/trees/" +
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

    def test_get_text(self):
        doc = xml.dom.minidom.parseString("""
            <parent>
                <child>
                    hi
                    <grandchild>1</grandchild>
                    <grandchild>2</grandchild>
                </child>
            </parent>""".strip())
        s = self.attachSVNPoller('http://', split_file=split_file)

        self.assertEqual(s._get_text(doc, 'grandchild'), '1')
        self.assertEqual(s._get_text(doc, 'nonexistent'), 'unknown')

    def test_create_changes(self):
        base = ("file:///home/warner/stuff/Projects/Buildbot/trees/" +
                "svnpoller/_trial_temp/test_vc/repositories/SVN-Repository/sample")
        s = self.attachSVNPoller(base, split_file=split_file)
        s._prefix = "sample"

        logentries = dict(
            zip(range(1, 7), reversed(make_logentry_elements(6))))
        changes = s.create_changes(reversed([logentries[3], logentries[2]]))
        self.assertEqual(len(changes), 2)
        # note that parsing occurs in reverse
        self.assertEqual(changes[0]['branch'], "branch")
        self.assertEqual(changes[0]['revision'], '2')
        self.assertEqual(changes[0]['project'], '')
        self.assertEqual(changes[0]['repository'], base)
        self.assertEqual(changes[1]['branch'], "branch")
        self.assertEqual(changes[1]['files'], ["main.c"])
        self.assertEqual(changes[1]['revision'], '3')
        self.assertEqual(changes[1]['project'], '')
        self.assertEqual(changes[1]['repository'], base)

        changes = s.create_changes([logentries[4]])
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['branch'], None)
        self.assertEqual(changes[0]['revision'], '4')
        self.assertEqual(changes[0]['files'], ["version.c"])

        # r5 should *not* create a change as it's a branch deletion
        changes = s.create_changes([logentries[5]])
        self.assertEqual(len(changes), 0)

        # r6 should create a change as it's not deleting an entire branch
        changes = s.create_changes([logentries[6]])
        self.assertEqual(len(changes), 1)
        self.assertEqual(changes[0]['branch'], 'branch')
        self.assertEqual(changes[0]['revision'], '6')
        self.assertEqual(changes[0]['files'], ["version.c"])

    def makeInfoExpect(self, password='bbrocks'):
        args = ['svn', 'info', '--xml', '--non-interactive', sample_base,
                '--username=dustin']
        if password is not None:
            args.append('--password=' + password)
        return gpo.Expect(*args)

    def makeLogExpect(self, password='bbrocks'):
        args = ['svn', 'log', '--xml', '--verbose', '--non-interactive',
                '--username=dustin']
        if password is not None:
            args.append('--password=' + password)
        args.extend(['--limit=100', sample_base])
        return gpo.Expect(*args)

    def test_create_changes_overridden_project(self):
        def custom_split_file(path):
            f = split_file(path)
            if f:
                f["project"] = "overridden-project"
                f["repository"] = "overridden-repository"
                f["codebase"] = "overridden-codebase"
            return f

        base = ("file:///home/warner/stuff/Projects/Buildbot/trees/" +
                "svnpoller/_trial_temp/test_vc/repositories/SVN-Repository/sample")
        s = self.attachSVNPoller(base, split_file=custom_split_file)
        s._prefix = "sample"

        logentries = dict(
            zip(range(1, 7), reversed(make_logentry_elements(6))))
        changes = s.create_changes(reversed([logentries[3], logentries[2]]))
        self.assertEqual(len(changes), 2)

        # note that parsing occurs in reverse
        self.assertEqual(changes[0]['branch'], "branch")
        self.assertEqual(changes[0]['revision'], '2')
        self.assertEqual(changes[0]['project'], "overridden-project")
        self.assertEqual(changes[0]['repository'], "overridden-repository")
        self.assertEqual(changes[0]['codebase'], "overridden-codebase")

        self.assertEqual(changes[1]['branch'], "branch")
        self.assertEqual(changes[1]['files'], ["main.c"])
        self.assertEqual(changes[1]['revision'], '3')
        self.assertEqual(changes[1]['project'], "overridden-project")
        self.assertEqual(changes[1]['repository'], "overridden-repository")
        self.assertEqual(changes[1]['codebase'], "overridden-codebase")

    def test_poll(self):
        s = self.attachSVNPoller(sample_base, split_file=split_file,
                                 svnuser='dustin', svnpasswd='bbrocks')

        d = defer.succeed(None)

        self.expectCommands(
            self.makeInfoExpect().stdout(sample_info_output),
            self.makeLogExpect().stdout(make_changes_output(1)),
            self.makeLogExpect().stdout(make_changes_output(1)),
            self.makeLogExpect().stdout(make_changes_output(2)),
            self.makeLogExpect().stdout(make_changes_output(4)),
        )
        # fire it the first time; it should do nothing
        d.addCallback(lambda _: s.poll())

        def check_first(_):
            # no changes generated on the first iteration
            self.assertEqual(self.master.data.updates.changesAdded, [])
            self.assertEqual(s.last_change, 1)
        d.addCallback(check_first)

        # now fire it again, nothing changing
        d.addCallback(lambda _: s.poll())

        def check_second(_):
            self.assertEqual(self.master.data.updates.changesAdded, [])
            self.assertEqual(s.last_change, 1)
        d.addCallback(check_second)

        # and again, with r2 this time
        d.addCallback(lambda _: s.poll())

        def check_third(_):
            self.assertEqual(self.master.data.updates.changesAdded, [{
                'author': u'warner',
                'branch': 'branch',
                'category': None,
                'codebase': None,
                'comments': u'make_branch',
                'files': [''],
                'project': '',
                'properties': {},
                'repository': 'file:///usr/home/warner/stuff/Projects/Buildbot/trees/misc/_trial_temp/test_vc/repositories/SVN-Repository/sample',
                'revision': '2',
                'revlink': '',
                'src': 'svn',
                'when_timestamp': None,
            }])
            self.assertEqual(s.last_change, 2)
        d.addCallback(check_third)

        # and again with both r3 and r4 appearing together
        def setup_fourth(_):
            self.master.data.updates.changesAdded = []
        d.addCallback(setup_fourth)
        d.addCallback(lambda _: s.poll())

        def check_fourth(_):
            self.assertEqual(self.master.data.updates.changesAdded, [{
                'author': u'warner',
                'branch': 'branch',
                'category': None,
                'codebase': None,
                'comments': u'commit_on_branch',
                'files': ['main.c'],
                'project': '',
                'properties': {},
                'repository': 'file:///usr/home/warner/stuff/Projects/Buildbot/trees/misc/_trial_temp/test_vc/repositories/SVN-Repository/sample',
                'revision': '3',
                'revlink': '',
                'src': 'svn',
                'when_timestamp': None,
            }, {
                'author': u'warner',
                'branch': None,
                'category': None,
                'codebase': None,
                'comments': u'revised_to_2',
                'files': ['version.c'],
                'project': '',
                'properties': {},
                'repository': 'file:///usr/home/warner/stuff/Projects/Buildbot/trees/misc/_trial_temp/test_vc/repositories/SVN-Repository/sample',
                'revision': '4',
                'revlink': '',
                'src': 'svn',
                'when_timestamp': None,
            }])
            self.assertEqual(s.last_change, 4)
            self.assertAllCommandsRan()
        d.addCallback(check_fourth)

        return d

    def test_poll_empty_password(self):
        s = self.attachSVNPoller(sample_base, split_file=split_file,
                                 svnuser='dustin', svnpasswd='')

        self.expectCommands(
            self.makeInfoExpect(password="").stdout(sample_info_output),
            self.makeLogExpect(password="").stdout(make_changes_output(1)),
            self.makeLogExpect(password="").stdout(make_changes_output(1)),
            self.makeLogExpect(password="").stdout(make_changes_output(2)),
            self.makeLogExpect(password="").stdout(make_changes_output(4)),
        )
        s.poll()

    def test_poll_no_password(self):
        s = self.attachSVNPoller(sample_base, split_file=split_file,
                                 svnuser='dustin')

        self.expectCommands(
            self.makeInfoExpect(password=None).stdout(sample_info_output),
            self.makeLogExpect(password=None).stdout(make_changes_output(1)),
            self.makeLogExpect(password=None).stdout(make_changes_output(1)),
            self.makeLogExpect(password=None).stdout(make_changes_output(2)),
            self.makeLogExpect(password=None).stdout(make_changes_output(4)),
        )
        s.poll()

    def test_poll_get_prefix_exception(self):
        s = self.attachSVNPoller(sample_base, split_file=split_file,
                                 svnuser='dustin', svnpasswd='bbrocks')

        self.expectCommands(
            self.makeInfoExpect().stderr("error"))
        d = s.poll()

        @d.addCallback
        def check(_):
            # should have logged the RuntimeError, but not errback'd from poll
            self.assertEqual(len(self.flushLoggedErrors(IOError)), 1)
            self.assertAllCommandsRan()
        return d

    def test_poll_get_logs_exception(self):
        s = self.attachSVNPoller(sample_base, split_file=split_file,
                                 svnuser='dustin', svnpasswd='bbrocks')
        s._prefix = "abc"  # skip the get_prefix stuff

        self.expectCommands(
            self.makeLogExpect().stderr("some error"))
        d = s.poll()

        @d.addCallback
        def check(_):
            # should have logged the RuntimeError, but not errback'd from poll
            self.assertEqual(len(self.flushLoggedErrors(IOError)), 1)
            self.assertAllCommandsRan()
        return d

    def test_cachepath_empty(self):
        cachepath = os.path.abspath('revcache')
        if os.path.exists(cachepath):
            os.unlink(cachepath)
        s = self.attachSVNPoller(sample_base, cachepath=cachepath)
        self.assertEqual(s.last_change, None)

    def test_cachepath_full(self):
        cachepath = os.path.abspath('revcache')
        with open(cachepath, "w") as f:
            f.write('33')
        s = self.attachSVNPoller(sample_base, cachepath=cachepath)
        self.assertEqual(s.last_change, 33)

        s.last_change = 44
        s.finished_ok(None)
        with open(cachepath) as f:
            self.assertEqual(f.read().strip(), '44')

    def test_cachepath_bogus(self):
        cachepath = os.path.abspath('revcache')
        with open(cachepath, "w") as f:
            f.write('nine')
        s = self.attachSVNPoller(sample_base, cachepath=cachepath)
        self.assertEqual(s.last_change, None)
        self.assertEqual(s.cachepath, None)
        # it should have called log.err once with a ValueError
        self.assertEqual(len(self.flushLoggedErrors(ValueError)), 1)

    def test_constructor_pollinterval(self):
        self.attachSVNPoller(sample_base, pollinterval=100)  # just don't fail!

    def test_extra_args(self):
        extra_args = ['--no-auth-cache', ]
        base = "svn+ssh://svn.twistedmatrix.com/svn/Twisted/trunk"

        s = self.attachSVNPoller(repourl=base, extra_args=extra_args)
        self.assertEqual(s.extra_args, extra_args)

    def test_use_svnurl(self):
        base = "svn+ssh://svn.twistedmatrix.com/svn/Twisted/trunk"
        self.assertRaises(TypeError, self.attachSVNPoller, svnurl=base)


class TestSplitFile(unittest.TestCase):

    def test_split_file_alwaystrunk(self):
        self.assertEqual(
            svnpoller.split_file_alwaystrunk('foo'), dict(path='foo'))

    def test_split_file_branches_trunk(self):
        self.assertEqual(
            svnpoller.split_file_branches('trunk/'),
            (None, ''))

    def test_split_file_branches_trunk_subdir(self):
        self.assertEqual(
            svnpoller.split_file_branches('trunk/subdir/'),
            (None, 'subdir/'))

    def test_split_file_branches_trunk_subfile(self):
        self.assertEqual(
            svnpoller.split_file_branches('trunk/subdir/file.c'),
            (None, 'subdir/file.c'))

    def test_split_file_branches_trunk_invalid(self):
        # file named trunk (not a directory):
        self.assertEqual(
            svnpoller.split_file_branches('trunk'),
            None)

    def test_split_file_branches_branch(self):
        self.assertEqual(
            svnpoller.split_file_branches('branches/1.5.x/'),
            ('branches/1.5.x', ''))

    def test_split_file_branches_branch_subdir(self):
        self.assertEqual(
            svnpoller.split_file_branches('branches/1.5.x/subdir/'),
            ('branches/1.5.x', 'subdir/'))

    def test_split_file_branches_branch_subfile(self):
        self.assertEqual(
            svnpoller.split_file_branches('branches/1.5.x/subdir/file.c'),
            ('branches/1.5.x', 'subdir/file.c'))

    def test_split_file_branches_branch_invalid(self):
        # file named branches/1.5.x (not a directory):
        self.assertEqual(
            svnpoller.split_file_branches('branches/1.5.x'),
            None)

    def test_split_file_branches_otherdir(self):
        # other dirs are ignored:
        self.assertEqual(
            svnpoller.split_file_branches('tags/testthis/subdir/'),
            None)

    def test_split_file_branches_otherfile(self):
        # other files are ignored:
        self.assertEqual(
            svnpoller.split_file_branches('tags/testthis/subdir/file.c'),
            None)

    def test_split_file_projects_branches(self):
        self.assertEqual(
            svnpoller.split_file_projects_branches(
                'buildbot/trunk/subdir/file.c'),
            dict(project='buildbot', path='subdir/file.c'))
        self.assertEqual(
            svnpoller.split_file_projects_branches(
                'buildbot/branches/1.5.x/subdir/file.c'),
            dict(project='buildbot', branch='branches/1.5.x', path='subdir/file.c'))
        # tags are ignored:
        self.assertEqual(
            svnpoller.split_file_projects_branches(
                'buildbot/tags/testthis/subdir/file.c'),
            None)
