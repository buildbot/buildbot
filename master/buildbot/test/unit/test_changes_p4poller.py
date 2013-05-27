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
u"""Change 3 by bob@testclient on 2006/04/13 21:51:39

	short desc truncated because this is a long description.
    ASDF-GUI-P3-\u2018Upgrade Icon\u2019 disappears sometimes.
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
        return self.tearDownChangeSource()

    def add_p4_describe_result(self, number, result):
        self.expectCommands(
                gpo.Expect('p4', 'describe', '-s', str(number)).stdout(result))

    # tests

    def test_describe(self):
        self.attachChangeSource(
                P4Source(p4port=None, p4user=None,
                         p4base='//depot/myproject/',
                         split_file=lambda x: x.split('/', 1)))
        self.assertSubstring("p4source", self.changesource.describe())

    def test_name(self):
        # no name:
        cs1 = P4Source(p4port=None, p4user=None,
                         p4base='//depot/myproject/',
                         split_file=lambda x: x.split('/', 1))
        self.assertEqual("P4Source:None://depot/myproject/", cs1.name)

        # explicit name:
        cs2 = P4Source(p4port=None, p4user=None, name='MyName',
                         p4base='//depot/myproject/',
                         split_file=lambda x: x.split('/', 1))
        self.assertEqual("MyName", cs2.name)

    def do_test_poll_successful(self, **kwargs):
        encoding = kwargs.get('encoding', 'utf8')
        self.attachChangeSource(
                P4Source(p4port=None, p4user=None,
                         p4base='//depot/myproject/',
                         split_file=lambda x: x.split('/', 1),
                         **kwargs))
        self.expectCommands(
                gpo.Expect('p4', 'changes', '-m', '1', '//depot/myproject/...').stdout(first_p4changes),
                gpo.Expect('p4', 'changes', '//depot/myproject/...@2,now').stdout(second_p4changes),
                )
        encoded_p4change = p4change.copy()
        encoded_p4change[3] = encoded_p4change[3].encode(encoding)
        self.add_p4_describe_result(2, encoded_p4change[2])
        self.add_p4_describe_result(3, encoded_p4change[3])

        # The first time, it just learns the change to start at.
        self.assert_(self.changesource.last_change is None)
        d = self.changesource.poll()
        def check_first_check(_):
            self.assertEquals(self.master.data.updates.changesAdded, [])
            self.assertEquals(self.changesource.last_change, 1)
        d.addCallback(check_first_check)

        # Subsequent times, it returns Change objects for new changes.
        d.addCallback(lambda _ : self.changesource.poll())
        def check_second_check(res):

            # when_timestamp is converted from a local time spec, so just
            # replicate that here
            when1 = "2006/04/13 21:46:23"
            when1 = int(time.mktime(time.strptime(when1, '%Y/%m/%d %H:%M:%S')))
            when2 = "2006/04/13 21:51:39"
            when2 = int(time.mktime(time.strptime(when2, '%Y/%m/%d %H:%M:%S')))

            # these two can happen in either order, since they're from the same
            # perforce change.
            changesAdded = self.master.data.updates.changesAdded
            if changesAdded[1]['branch'] == 'branch_c':
                changesAdded[1:] = reversed(changesAdded[1:])
            self.assertEqual(self.master.data.updates.changesAdded, [ {
                'author': u'slamb',
                'branch': u'trunk',
                'category': None,
                'codebase': None,
                'comments': u'Change 2 by slamb@testclient on 2006/04/13 21:46:23\n\n\tcreation\n',
                'files': [u'whatbranch'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': '2',
                'revlink': '',
                'src': None,
                'when_timestamp': when1,
            }, {
                'author': u'bob',
                'branch': u'branch_b',
                'category': None,
                'codebase': None,
                'comments': u'Change 3 by bob@testclient on 2006/04/13 21:51:39\n\n\tshort desc truncated because this is a long description.\n    ASDF-GUI-P3-\u2018Upgrade Icon\u2019 disappears sometimes.\n',
                'files': [u'branch_b_file', u'whatbranch'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': '3',
                'revlink': '',
                'src': None,
                'when_timestamp': when2,
            }, {
                'author': u'bob',
                'branch': u'branch_c',
                'category': None,
                'codebase': None,
                'comments': u'Change 3 by bob@testclient on 2006/04/13 21:51:39\n\n\tshort desc truncated because this is a long description.\n    ASDF-GUI-P3-\u2018Upgrade Icon\u2019 disappears sometimes.\n',
                'files': [u'whatbranch'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': '3',
                'revlink': '',
                'src': None,
                'when_timestamp': when2,
            }])
            self.assertAllCommandsRan()
        d.addCallback(check_second_check)
        return d

    def test_poll_successful_default_encoding(self):
        return self.do_test_poll_successful()

    def test_poll_successful_macroman_encoding(self):
        return self.do_test_poll_successful(encoding='macroman')

    def test_poll_failed_changes(self):
        self.attachChangeSource(
                P4Source(p4port=None, p4user=None,
                         p4base='//depot/myproject/',
                         split_file=lambda x: x.split('/', 1)))
        self.expectCommands(
                gpo.Expect('p4', 'changes', '-m', '1', '//depot/myproject/...').stdout('Perforce client error:\n...'))

        # call _poll, so we can catch the failure
        d = self.changesource._poll()
        return self.assertFailure(d, P4PollerError)

    def test_poll_failed_describe(self):
        self.attachChangeSource(
                P4Source(p4port=None, p4user=None,
                         p4base='//depot/myproject/',
                         split_file=lambda x: x.split('/', 1)))
        self.expectCommands(
                gpo.Expect('p4', 'changes', '//depot/myproject/...@3,now').stdout(second_p4changes),
                )
        self.add_p4_describe_result(2, p4change[2])
        self.add_p4_describe_result(3, 'Perforce client error:\n...')

        self.changesource.last_change = 2 # tell poll() that it's already been called once

        # call _poll, so we can catch the failure
        d = self.changesource._poll()
        self.assertFailure(d, P4PollerError)
        @d.addCallback
        def check(_):
            # check that 2 was processed OK
            self.assertEquals(self.changesource.last_change, 2)
            self.assertAllCommandsRan()
        return d

    def test_poll_split_file(self):
        """Make sure split file works on branch only changes"""
        self.attachChangeSource(
                P4Source(p4port=None, p4user=None,
                         p4base='//depot/myproject/',
                         split_file=get_simple_split))
        self.expectCommands(
                gpo.Expect('p4', 'changes', '//depot/myproject/...@51,now').stdout(third_p4changes),
                )
        self.add_p4_describe_result(5, p4change[5])

        self.changesource.last_change = 50
        d = self.changesource.poll()
        def check(res):
            # when_timestamp is converted from a local time spec, so just
            # replicate that here
            when = "2006/04/13 21:55:39"
            when = int(time.mktime(time.strptime(when, '%Y/%m/%d %H:%M:%S')))

            self.assertEqual(self.master.data.updates.changesAdded, [{
                'author': u'mpatel',
                'branch': u'branch_c',
                'category': None,
                'codebase': None,
                'comments': u'Change 4 by mpatel@testclient on 2006/04/13 21:55:39\n\n\tshort desc truncated because this is a long description.\n',
                'files': [u'branch_c_file'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': '5',
                'revlink': '',
                'src': None,
                'when_timestamp': when,
            }, {
                'author': u'mpatel',
                'branch': u'branch_b',
                'category': None,
                'codebase': None,
                'comments': u'Change 4 by mpatel@testclient on 2006/04/13 21:55:39\n\n\tshort desc truncated because this is a long description.\n',
                'files': [u'branch_b_file'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': '5',
                'revlink': '',
                'src': None,
                'when_timestamp': when,
                }])
            self.assertEquals(self.changesource.last_change, 5)
            self.assertAllCommandsRan()
        d.addCallback(check)
        return d

class TestSplit(unittest.TestCase):
    def test_get_simple_split(self):
        self.assertEqual(get_simple_split('foo/bar'), ('foo', 'bar'))
        self.assertEqual(get_simple_split('foo-bar'), (None, None))
        self.assertEqual(get_simple_split('/bar'), ('', 'bar'))
        self.assertEqual(get_simple_split('foo/'), ('foo', ''))
