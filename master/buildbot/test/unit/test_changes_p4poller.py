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

import datetime

from buildbot.changes.p4poller import P4PollerError
from buildbot.changes.p4poller import P4Source
from buildbot.changes.p4poller import get_simple_split
from buildbot.test.util import changesource
from buildbot.test.util import gpo
from twisted.internet import error
from twisted.internet import reactor
from twisted.python import failure
from twisted.trial import unittest

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

    def makeTime(self, timestring):
        datefmt = '%Y/%m/%d %H:%M:%S'
        when = datetime.datetime.strptime(timestring, datefmt)
        return when

    # tests

    def test_describe(self):
        self.attachChangeSource(
            P4Source(p4port=None, p4user=None,
                     p4base='//depot/myproject/',
                     split_file=lambda x: x.split('/', 1)))
        self.assertSubstring("p4source", self.changesource.describe())

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
            self.assertEquals(self.changes_added, [])
            self.assertEquals(self.changesource.last_change, 1)
        d.addCallback(check_first_check)

        # Subsequent times, it returns Change objects for new changes.
        d.addCallback(lambda _: self.changesource.poll())

        def check_second_check(res):
            self.assertEquals(len(self.changes_added), 3)
            self.assertEquals(self.changesource.last_change, 3)

            # They're supposed to go oldest to newest, so this one must be first.
            self.assertEquals(self.changes_added[0],
                              dict(author='slamb',
                                   files=['whatbranch'],
                                   project='',
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
                                   project='',
                                   comments=change_3_log,  # converted to unicode correctly
                                   revision='3',
                                   when_timestamp=self.makeTime("2006/04/13 21:51:39"),
                                   branch='branch_b'))
            self.assertEquals(self.changes_added[2],
                              dict(author='bob',
                                   files=['whatbranch'],
                                   project='',
                                   comments=change_3_log,  # converted to unicode correctly
                                   revision='3',
                                   when_timestamp=self.makeTime("2006/04/13 21:51:39"),
                                   branch='branch_c'))
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

        self.changesource.last_change = 2  # tell poll() that it's already been called once

        # call _poll, so we can catch the failure
        d = self.changesource._poll()
        self.assertFailure(d, P4PollerError)

        @d.addCallback
        def check(_):
            # check that 2 was processed OK
            self.assertEquals(self.changesource.last_change, 2)
            self.assertAllCommandsRan()
        return d

    def test_acquire_ticket_auth(self):
        self.attachChangeSource(
            P4Source(p4port=None, p4user=None, p4passwd='pass',
                     p4base='//depot/myproject/',
                     split_file=lambda x: x.split('/', 1),
                     use_tickets=True))
        self.expectCommands(
            gpo.Expect('p4', '-P', 'TICKET_ID_GOES_HERE',
                       'changes', '-m', '1', '//depot/myproject/...').stdout(first_p4changes)
        )

        class FakeTransport:

            def __init__(self):
                self.msg = None

            def write(self, msg):
                self.msg = msg

            def closeStdin(self):
                pass

        transport = FakeTransport()

        def spawnProcess(pp, cmd, argv, env):  # p4poller uses only those arguments at the moment
            self.assertEqual([cmd, argv],
                             ['p4', ['p4', 'login', '-p']])
            pp.makeConnection(transport)
            self.assertEqual('pass\n', transport.msg)
            pp.outReceived('Enter password:\nTICKET_ID_GOES_HERE\n')
            so = error.ProcessDone(None)
            pp.processEnded(failure.Failure(so))
        self.patch(reactor, 'spawnProcess', spawnProcess)

        d = self.changesource.poll()

        def check_ticket_passwd(_):
            self.assertEquals(self.changesource._ticket_passwd, 'TICKET_ID_GOES_HERE')
        d.addCallback(check_ticket_passwd)
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
            self.assertEquals(len(self.changes_added), 2)
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
