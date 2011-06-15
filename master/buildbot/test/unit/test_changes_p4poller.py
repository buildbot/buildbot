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

import time
from twisted.trial import unittest
from buildbot.changes.p4poller import P4Source, get_simple_split, P4PollerError
from buildbot.test.util import changesource, gpo
from buildbot.util import epoch2datetime

first_p4changes = \
"""Change 1 on 2006/04/13 by slamb@testclient 'first rev'
"""

second_p4changes = \
"""Change 3 on 2006/04/13 by bob@testclient 'short desc truncated'
Change 2 on 2006/04/13 by slamb@testclient 'bar'
"""

third_p4changes = \
"""Change 5 on 2006/04/13 by mpatel@testclient 'first rev'
"""

change_4_log = \
"""Change 4 by mpatel@testclient on 2006/04/13 21:55:39

	short desc truncated because this is a long description.
"""
change_3_log = \
"""Change 3 by bob@testclient on 2006/04/13 21:51:39

	short desc truncated because this is a long description.
"""

change_2_log = \
"""Change 2 by slamb@testclient on 2006/04/13 21:46:23

	creation
"""

p4change = {
    3: change_3_log +
"""Affected files ...

... //depot/myproject/branch_b/branch_b_file#1 add
... //depot/myproject/branch_b/whatbranch#1 branch
... //depot/myproject/branch_c/whatbranch#1 branch
""",
    2: change_2_log +
"""Affected files ...

... //depot/myproject/trunk/whatbranch#1 add
... //depot/otherproject/trunk/something#1 add
""",
    5: change_4_log +
"""Affected files ...

... //depot/myproject/branch_b/branch_b_file#1 add
... //depot/myproject/branch_b#75 edit
... //depot/myproject/branch_c/branch_c_file#1 add
""",
}


class TestP4Poller(changesource.ChangeSourceMixin,
                   gpo.GetProcessOutputMixin,
                   unittest.TestCase):
    def setUp(self):
        self.setUpGetProcessOutput()
        return self.setUpChangeSource()

    def tearDown(self):
        self.tearDownGetProcessOutput()
        return self.tearDownChangeSource()

    def add_p4_changes_result(self, result):
        self.addGetProcessOutputResult(
                self.gpoSubcommandPattern('p4', 'changes'),
                result)

    def add_p4_describe_result(self, number, result):
        def match(bin, args, **kwargs):
            if not bin.endswith('p4'):
                return False
            if 'describe' not in args:
                return False
            s_idx = args.index('-s')
            if s_idx < 0:
                return False
            got_num = int(args[s_idx+1])
            if got_num != number:
                return False
            return True
        self.addGetProcessOutputResult(match, result)

    def update_p4_describe_results(self, dict):
        for number, result in dict.items():
            self.add_p4_describe_result(number, result)

    def makeTime(self, timestring):
        datefmt = '%Y/%m/%d %H:%M:%S'
        when = time.mktime(time.strptime(timestring, datefmt))
        return epoch2datetime(when)

    # tests

    def test_describe(self):
        self.attachChangeSource(
                P4Source(p4port=None, p4user=None,
                         p4base='//depot/myproject/',
                         split_file=lambda x: x.split('/', 1)))
        self.assertSubstring("p4source", self.changesource.describe())

    def test_poll_successful(self):
        self.attachChangeSource(
                P4Source(p4port=None, p4user=None,
                         p4base='//depot/myproject/',
                         split_file=lambda x: x.split('/', 1)))
        self.add_p4_changes_result(first_p4changes)
        self.add_p4_changes_result(second_p4changes)
        self.update_p4_describe_results(p4change)

        # The first time, it just learns the change to start at.
        self.assert_(self.changesource.last_change is None)
        d = self.changesource.poll()
        def check_first_check(_):
            self.assertEquals(self.changes_added, [])
            self.assertEquals(self.changesource.last_change, 1)
        d.addCallback(check_first_check)

        # Subsequent times, it returns Change objects for new changes.
        d.addCallback(lambda _ : self.changesource.poll())
        def check_second_check(res):
            self.assertEquals(len(self.changes_added), 3)
            self.assertEquals(self.changesource.last_change, 3)

            # They're supposed to go oldest to newest, so this one must be first.
            self.assertEquals(self.changes_added[0],
                dict(author='slamb',
                     files=['whatbranch'],
                     comments=change_2_log,
                     revision='2',
                     when_timestamp=self.makeTime("2006/04/13 21:46:23"),
                     branch='trunk'))

            # These two can happen in either order, since they're from the same
            # Perforce change.
            if self.changes_added[1]['branch'] == 'branch_c':
                self.changes_added[1:] = reversed(self.changes_added[1:])

            self.assertEquals(self.changes_added[1],
                dict(author='bob',
                     files=['branch_b_file',
                            'whatbranch'],
                     comments=change_3_log,
                     revision='3',
                     when_timestamp=self.makeTime("2006/04/13 21:51:39"),
                     branch='branch_b'))
            self.assertEquals(self.changes_added[2],
                dict(author='bob',
                     files=['whatbranch'],
                     comments=change_3_log,
                     revision='3',
                     when_timestamp=self.makeTime("2006/04/13 21:51:39"),
                     branch='branch_c'))
        d.addCallback(check_second_check)
        return d

    def test_poll_failed_changes(self):
        self.attachChangeSource(
                P4Source(p4port=None, p4user=None,
                         p4base='//depot/myproject/',
                         split_file=lambda x: x.split('/', 1)))
        self.add_p4_changes_result('Perforce client error:\n...')

        # call _poll, so we can catch the failure
        d = self.changesource._poll()
        def cb(_):
            self.fail("_poll should have failed")
        def eb(f):
            f.trap(P4PollerError)
            self.assertEquals(self.changesource.last_change, None)
        d.addCallbacks(cb, eb)
        return d

    def test_poll_failed_describe(self):
        self.attachChangeSource(
                P4Source(p4port=None, p4user=None,
                         p4base='//depot/myproject/',
                         split_file=lambda x: x.split('/', 1)))
        self.add_p4_changes_result(second_p4changes)
        self.add_p4_describe_result(3, 'Perforce client error:\n...')
        self.update_p4_describe_results(p4change) # note change 3 is overridden by prev line

        self.changesource.last_change = 2 # tell poll() that it's already been called once

        # call _poll, so we can catch the failure
        d = self.changesource._poll()
        def cb(_):
            self.fail("_poll should have failed")
        def eb(f):
            f.trap(P4PollerError)
            self.assertEquals(self.changesource.last_change, 2) # 2 was processed OK
        d.addCallbacks(cb, eb)
        return d

    def test_poll_split_file(self):
        """Make sure split file works on branch only changes"""
        self.attachChangeSource(
                P4Source(p4port=None, p4user=None,
                         p4base='//depot/myproject/',
                         split_file=get_simple_split))
        self.add_p4_changes_result(third_p4changes)
        self.update_p4_describe_results(p4change)

        self.changesource.last_change = 50
        d = self.changesource.poll()
        def check(res):
            self.assertEquals(len(self.changes_added), 2)
            self.assertEquals(self.changesource.last_change, 5)
        d.addCallback(check)
        return d

class TestSplit(unittest.TestCase):
    def test_get_simple_split(self):
        self.assertEqual(get_simple_split('foo/bar'), ('foo', 'bar'))
        self.assertEqual(get_simple_split('foo-bar'), (None, None))
        self.assertEqual(get_simple_split('/bar'), ('', 'bar'))
        self.assertEqual(get_simple_split('foo/'), ('foo', ''))
