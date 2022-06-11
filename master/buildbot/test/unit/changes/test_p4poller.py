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

import dateutil.tz

from twisted.internet import defer
from twisted.internet import error
from twisted.internet import reactor
from twisted.python import failure
from twisted.trial import unittest

from buildbot.changes.p4poller import P4PollerError
from buildbot.changes.p4poller import P4Source
from buildbot.changes.p4poller import get_simple_split
from buildbot.test.reactor import TestReactorMixin
from buildbot.test.runprocess import ExpectMasterShell
from buildbot.test.runprocess import MasterRunProcessMixin
from buildbot.test.util import changesource
from buildbot.test.util import config
from buildbot.util import datetime2epoch

first_p4changes = \
    b"""Change 1 on 2006/04/13 by slamb@testclient 'first rev'
"""

second_p4changes = \
    b"""Change 3 on 2006/04/13 by bob@testclient 'short desc truncated'
Change 2 on 2006/04/13 by slamb@testclient 'bar'
"""

third_p4changes = \
    b"""Change 5 on 2006/04/13 by mpatel@testclient 'first rev'
"""

fourth_p4changes = \
    b"""Change 6 on 2006/04/14 by mpatel@testclient 'bar \xd0\x91'
"""

p4_describe_2 = \
    b"""Change 2 by slamb@testclient on 2006/04/13 21:46:23

\tcreation

Affected files ...

... //depot/myproject/trunk/whatbranch#1 add
... //depot/otherproject/trunk/something#1 add
"""

p4_describe_3 = \
    """Change 3 by bob@testclient on 2006/04/13 21:51:39

\tshort desc truncated because this is a long description.
\tASDF-GUI-P3-\u2018Upgrade Icon\u2019 disappears sometimes.

Affected files ...

... //depot/myproject/branch_b/branch_b_file#1 add
... //depot/myproject/branch_b/whatbranch#1 branch
... //depot/myproject/branch_c/whatbranch#1 branch
"""

p4_describe_4 = \
    b"""Change 4 by mpatel@testclient on 2006/04/13 21:55:39

\tThis is a multiline comment with tabs and spaces
\t
\tA list:
\t  Item 1
\t\tItem 2

Affected files ...

... //depot/myproject/branch_b/branch_b_file#1 add
... //depot/myproject/branch_b#75 edit
... //depot/myproject/branch_c/branch_c_file#1 add
"""

p4change = {
    3: p4_describe_3,
    2: p4_describe_2,
    5: p4_describe_4,
}


class FakeTransport:

    def __init__(self):
        self.msg = None

    def write(self, msg):
        self.msg = msg

    def closeStdin(self):
        pass


class TestP4Poller(changesource.ChangeSourceMixin, MasterRunProcessMixin,
                   config.ConfigErrorsMixin,
                   TestReactorMixin,
                   unittest.TestCase):

    @defer.inlineCallbacks
    def setUp(self):
        self.setup_test_reactor()
        self.setup_master_run_process()
        yield self.setUpChangeSource()

    def tearDown(self):
        return self.tearDownChangeSource()

    def add_p4_describe_result(self, number, result):
        self.expect_commands(
            ExpectMasterShell(['p4', 'describe', '-s', str(number)])
            .stdout(result)
        )

    def makeTime(self, timestring):
        datefmt = '%Y/%m/%d %H:%M:%S'
        when = datetime.datetime.strptime(timestring, datefmt)
        return when

    @defer.inlineCallbacks
    def test_describe(self):
        yield self.attachChangeSource(
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

    @defer.inlineCallbacks
    def do_test_poll_successful(self, **kwargs):
        encoding = kwargs.get('encoding', 'utf8')
        yield self.attachChangeSource(
            P4Source(p4port=None, p4user=None,
                     p4base='//depot/myproject/',
                     split_file=lambda x: x.split('/', 1),
                     **kwargs))
        self.expect_commands(
            ExpectMasterShell(['p4', 'changes', '-m', '1', '//depot/myproject/...'])
            .stdout(first_p4changes),

            ExpectMasterShell(['p4', 'changes', '//depot/myproject/...@2,#head'])
            .stdout(second_p4changes),
        )
        encoded_p4change = p4change.copy()
        encoded_p4change[3] = encoded_p4change[3].encode(encoding)
        self.add_p4_describe_result(2, encoded_p4change[2])
        self.add_p4_describe_result(3, encoded_p4change[3])

        # The first time, it just learns the change to start at.
        self.assertTrue(self.changesource.last_change is None)
        yield self.changesource.poll()

        self.assertEqual(self.master.data.updates.changesAdded, [])
        self.assertEqual(self.changesource.last_change, 1)

        # Subsequent times, it returns Change objects for new changes.
        yield self.changesource.poll()

        # when_timestamp is converted from a local time spec, so just
        # replicate that here
        when1 = self.makeTime("2006/04/13 21:46:23")
        when2 = self.makeTime("2006/04/13 21:51:39")

        # these two can happen in either order, since they're from the same
        # perforce change.
        changesAdded = self.master.data.updates.changesAdded
        if changesAdded[1]['branch'] == 'branch_c':
            changesAdded[1:] = reversed(changesAdded[1:])
        self.assertEqual(self.master.data.updates.changesAdded, [{
            'author': 'slamb',
            'committer': None,
            'branch': 'trunk',
            'category': None,
            'codebase': None,
            'comments': 'creation',
            'files': ['whatbranch'],
            'project': '',
            'properties': {},
            'repository': '',
            'revision': '2',
            'revlink': '',
            'src': None,
            'when_timestamp': datetime2epoch(when1),
        }, {
            'author': 'bob',
            'committer': None,
            'branch': 'branch_b',
            'category': None,
            'codebase': None,
            'comments':
                'short desc truncated because this is a long description.\n'
                'ASDF-GUI-P3-\u2018Upgrade Icon\u2019 disappears sometimes.',
            'files': ['branch_b_file', 'whatbranch'],
            'project': '',
            'properties': {},
            'repository': '',
            'revision': '3',
            'revlink': '',
            'src': None,
            'when_timestamp': datetime2epoch(when2),
        }, {
            'author': 'bob',
            'committer': None,
            'branch': 'branch_c',
            'category': None,
            'codebase': None,
            'comments':
                'short desc truncated because this is a long description.\n'
                'ASDF-GUI-P3-\u2018Upgrade Icon\u2019 disappears sometimes.',
            'files': ['whatbranch'],
            'project': '',
            'properties': {},
            'repository': '',
            'revision': '3',
            'revlink': '',
            'src': None,
            'when_timestamp': datetime2epoch(when2),
        }])
        self.assert_all_commands_ran()

    def test_poll_successful_default_encoding(self):
        return self.do_test_poll_successful()

    def test_poll_successful_macroman_encoding(self):
        return self.do_test_poll_successful(encoding='macroman')

    @defer.inlineCallbacks
    def test_poll_failed_changes(self):
        yield self.attachChangeSource(
            P4Source(p4port=None, p4user=None,
                     p4base='//depot/myproject/',
                     split_file=lambda x: x.split('/', 1)))
        self.expect_commands(
            ExpectMasterShell(['p4', 'changes', '-m', '1', '//depot/myproject/...'])
            .stdout(b'Perforce client error:\n...')
        )

        # call _poll, so we can catch the failure
        with self.assertRaises(P4PollerError):
            yield self.changesource._poll()

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_poll_failed_describe(self):
        yield self.attachChangeSource(
            P4Source(p4port=None, p4user=None,
                     p4base='//depot/myproject/',
                     split_file=lambda x: x.split('/', 1)))
        self.expect_commands(
            ExpectMasterShell(['p4', 'changes', '//depot/myproject/...@3,#head'])
            .stdout(second_p4changes),
        )
        self.add_p4_describe_result(2, p4change[2])
        self.add_p4_describe_result(3, b'Perforce client error:\n...')

        # tell poll() that it's already been called once
        self.changesource.last_change = 2

        # call _poll, so we can catch the failure
        with self.assertRaises(P4PollerError):
            yield self.changesource._poll()

        # check that 2 was processed OK
        self.assertEqual(self.changesource.last_change, 2)
        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_poll_unicode_error(self):
        yield self.attachChangeSource(
            P4Source(p4port=None, p4user=None,
                     p4base='//depot/myproject/',
                     split_file=lambda x: x.split('/', 1)))
        self.expect_commands(
            ExpectMasterShell(['p4', 'changes', '//depot/myproject/...@3,#head'])
            .stdout(second_p4changes),
        )
        # Add a character which cannot be decoded with utf-8
        undecodableText = p4change[2] + b"\x81"
        self.add_p4_describe_result(2, undecodableText)

        # tell poll() that it's already been called once
        self.changesource.last_change = 2

        # call _poll, so we can catch the failure
        with self.assertRaises(UnicodeError):
            yield self.changesource._poll()

        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_poll_unicode_error2(self):
        yield self.attachChangeSource(
            P4Source(p4port=None, p4user=None,
                     p4base='//depot/myproject/',
                     split_file=lambda x: x.split('/', 1),
                     encoding='ascii'))
        # Trying to decode a certain character with ascii codec should fail.
        self.expect_commands(
            ExpectMasterShell(['p4', 'changes', '-m', '1', '//depot/myproject/...'])
            .stdout(fourth_p4changes),
        )

        yield self.changesource._poll()
        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_acquire_ticket_auth(self):
        yield self.attachChangeSource(
            P4Source(p4port=None, p4user='buildbot_user', p4passwd='pass',
                     p4base='//depot/myproject/',
                     split_file=lambda x: x.split('/', 1),
                     use_tickets=True))
        self.expect_commands(
            ExpectMasterShell(['p4', 'changes', '-m', '1', '//depot/myproject/...'])
            .stdout(first_p4changes)
        )

        transport = FakeTransport()

        # p4poller uses only those arguments at the moment
        def spawnProcess(pp, cmd, argv, env):
            self.assertEqual([cmd, argv],
                             ['p4', [b'p4', b'-u', b'buildbot_user', b'login']])
            pp.makeConnection(transport)
            self.assertEqual(b'pass\n', transport.msg)
            pp.outReceived(b'Enter password:\nUser buildbot_user logged in.\n')
            so = error.ProcessDone(None)
            pp.processEnded(failure.Failure(so))
        self.patch(reactor, 'spawnProcess', spawnProcess)

        yield self.changesource.poll()
        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_acquire_ticket_auth_fail(self):
        yield self.attachChangeSource(
            P4Source(p4port=None, p4user=None, p4passwd='pass',
                     p4base='//depot/myproject/',
                     split_file=lambda x: x.split('/', 1),
                     use_tickets=True))
        self.expect_commands(
            ExpectMasterShell(['p4', 'changes', '-m', '1', '//depot/myproject/...'])
            .stdout(first_p4changes)
        )

        transport = FakeTransport()

        # p4poller uses only those arguments at the moment
        def spawnProcess(pp, cmd, argv, env):
            self.assertEqual([cmd, argv],
                             ['p4', [b'p4', b'login']])
            pp.makeConnection(transport)
            self.assertEqual(b'pass\n', transport.msg)
            pp.outReceived(b'Enter password:\n')
            pp.errReceived(b"Password invalid.\n")
            so = error.ProcessDone(status=1)
            pp.processEnded(failure.Failure(so))
        self.patch(reactor, 'spawnProcess', spawnProcess)

        yield self.changesource.poll()

    @defer.inlineCallbacks
    def test_poll_split_file(self):
        """Make sure split file works on branch only changes"""
        yield self.attachChangeSource(
            P4Source(p4port=None, p4user=None,
                     p4base='//depot/myproject/',
                     split_file=get_simple_split))
        self.expect_commands(
            ExpectMasterShell(['p4', 'changes', '//depot/myproject/...@51,#head'])
            .stdout(third_p4changes),
        )
        self.add_p4_describe_result(5, p4change[5])

        self.changesource.last_change = 50
        yield self.changesource.poll()

        # when_timestamp is converted from a local time spec, so just
        # replicate that here
        when = self.makeTime("2006/04/13 21:55:39")

        def changeKey(change):
            """ Let's sort the array of changes by branch,
                because in P4Source._poll(), changeAdded()
                is called by iterating over a dictionary of
                branches"""
            return change['branch']

        self.assertEqual(sorted(self.master.data.updates.changesAdded, key=changeKey),
            sorted([{
            'author': 'mpatel',
            'committer': None,
            'branch': 'branch_c',
            'category': None,
            'codebase': None,
            'comments': 'This is a multiline comment with tabs and spaces\n\nA list:\n  '
                        'Item 1\n\tItem 2',
            'files': ['branch_c_file'],
            'project': '',
            'properties': {},
            'repository': '',
            'revision': '5',
            'revlink': '',
            'src': None,
            'when_timestamp': datetime2epoch(when),
        }, {
            'author': 'mpatel',
            'committer': None,
            'branch': 'branch_b',
            'category': None,
            'codebase': None,
            'comments': 'This is a multiline comment with tabs and spaces\n\nA list:\n  '
                        'Item 1\n\tItem 2',
            'files': ['branch_b_file'],
            'project': '',
            'properties': {},
            'repository': '',
            'revision': '5',
            'revlink': '',
            'src': None,
            'when_timestamp': datetime2epoch(when),
        }], key=changeKey))
        self.assertEqual(self.changesource.last_change, 5)
        self.assert_all_commands_ran()

    @defer.inlineCallbacks
    def test_server_tz(self):
        """Verify that the server_tz parameter is handled correctly"""
        yield self.attachChangeSource(
            P4Source(p4port=None, p4user=None,
                     p4base='//depot/myproject/',
                     split_file=get_simple_split,
                     server_tz="Europe/Berlin"))
        self.expect_commands(
            ExpectMasterShell(['p4', 'changes', '//depot/myproject/...@51,#head'])
            .stdout(third_p4changes),
        )
        self.add_p4_describe_result(5, p4change[5])

        self.changesource.last_change = 50
        yield self.changesource.poll()

        # when_timestamp is converted from 21:55:39 Berlin time to UTC
        when_berlin = self.makeTime("2006/04/13 21:55:39")
        when_berlin = when_berlin.replace(
            tzinfo=dateutil.tz.gettz('Europe/Berlin'))
        when = datetime2epoch(when_berlin)

        self.assertEqual([ch['when_timestamp']
                          for ch in self.master.data.updates.changesAdded],
                         [when, when])
        self.assert_all_commands_ran()

    def test_resolveWho_callable(self):
        with self.assertRaisesConfigError(
                "You need to provide a valid callable for resolvewho"):
            P4Source(resolvewho=None)


class TestSplit(unittest.TestCase):

    def test_get_simple_split(self):
        self.assertEqual(get_simple_split('foo/bar'), ('foo', 'bar'))
        self.assertEqual(get_simple_split('foo-bar'), (None, None))
        self.assertEqual(get_simple_split('/bar'), ('', 'bar'))
        self.assertEqual(get_simple_split('foo/'), ('foo', ''))
