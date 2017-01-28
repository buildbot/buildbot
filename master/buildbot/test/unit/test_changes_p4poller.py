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

import datetime

import dateutil.tz

from twisted.internet import error
from twisted.internet import reactor
from twisted.python import failure
from twisted.trial import unittest

from buildbot.changes.p4poller import P4PollerError
from buildbot.changes.p4poller import P4Source
from buildbot.changes.p4poller import get_simple_split
from buildbot.test.util import changesource
from buildbot.test.util import gpo
from buildbot.util import datetime2epoch

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

p4_describe_2 = \
    """Change 2 by slamb@testclient on 2006/04/13 21:46:23

\tcreation

Affected files ...

... //depot/myproject/trunk/whatbranch#1 add
... //depot/otherproject/trunk/something#1 add
"""

p4_describe_3 = \
    u"""Change 3 by bob@testclient on 2006/04/13 21:51:39

\tshort desc truncated because this is a long description.
\tASDF-GUI-P3-\u2018Upgrade Icon\u2019 disappears sometimes.

Affected files ...

... //depot/myproject/branch_b/branch_b_file#1 add
... //depot/myproject/branch_b/whatbranch#1 branch
... //depot/myproject/branch_c/whatbranch#1 branch
"""

p4_describe_4 = \
    """Change 4 by mpatel@testclient on 2006/04/13 21:55:39

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
            gpo.Expect(
                'p4', 'changes', '-m', '1', '//depot/myproject/...').stdout(first_p4changes),
            gpo.Expect(
                'p4', 'changes', '//depot/myproject/...@2,#head').stdout(second_p4changes),
        )
        encoded_p4change = p4change.copy()
        encoded_p4change[3] = encoded_p4change[3].encode(encoding)
        self.add_p4_describe_result(2, encoded_p4change[2])
        self.add_p4_describe_result(3, encoded_p4change[3])

        # The first time, it just learns the change to start at.
        self.assertTrue(self.changesource.last_change is None)
        d = self.changesource.poll()

        def check_first_check(_):
            self.assertEqual(self.master.data.updates.changesAdded, [])
            self.assertEqual(self.changesource.last_change, 1)
        d.addCallback(check_first_check)

        # Subsequent times, it returns Change objects for new changes.
        d.addCallback(lambda _: self.changesource.poll())

        def check_second_check(res):

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
                'author': u'slamb',
                'branch': u'trunk',
                'category': None,
                'codebase': None,
                'comments': u'creation',
                'files': [u'whatbranch'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': '2',
                'revlink': '',
                'src': None,
                'when_timestamp': datetime2epoch(when1),
            }, {
                'author': u'bob',
                'branch': u'branch_b',
                'category': None,
                'codebase': None,
                'comments': u'short desc truncated because this is a long description.\nASDF-GUI-P3-\u2018Upgrade Icon\u2019 disappears sometimes.',
                'files': [u'branch_b_file', u'whatbranch'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': '3',
                'revlink': '',
                'src': None,
                'when_timestamp': datetime2epoch(when2),
            }, {
                'author': u'bob',
                'branch': u'branch_c',
                'category': None,
                'codebase': None,
                'comments': u'short desc truncated because this is a long description.\nASDF-GUI-P3-\u2018Upgrade Icon\u2019 disappears sometimes.',
                'files': [u'whatbranch'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': '3',
                'revlink': '',
                'src': None,
                'when_timestamp': datetime2epoch(when2),
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
            gpo.Expect(
                'p4', 'changes', '//depot/myproject/...@3,#head').stdout(second_p4changes),
        )
        self.add_p4_describe_result(2, p4change[2])
        self.add_p4_describe_result(3, 'Perforce client error:\n...')

        # tell poll() that it's already been called once
        self.changesource.last_change = 2

        # call _poll, so we can catch the failure
        d = self.changesource._poll()
        self.assertFailure(d, P4PollerError)

        @d.addCallback
        def check(_):
            # check that 2 was processed OK
            self.assertEqual(self.changesource.last_change, 2)
            self.assertAllCommandsRan()
        return d

    def test_poll_unicode_error(self):
        self.attachChangeSource(
            P4Source(p4port=None, p4user=None,
                     p4base='//depot/myproject/',
                     split_file=lambda x: x.split('/', 1)))
        self.expectCommands(
            gpo.Expect(
                'p4', 'changes', '//depot/myproject/...@3,#head').stdout(second_p4changes),
        )
        # Add a character which cannot be decoded with utf-8
        undecodableText = p4change[2].encode("utf-8") + b"\x81"
        self.add_p4_describe_result(2, undecodableText)

        # tell poll() that it's already been called once
        self.changesource.last_change = 2

        # call _poll, so we can catch the failure
        d = self.changesource._poll()
        return self.assertFailure(d, UnicodeError)

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

        # p4poller uses only those arguments at the moment
        def spawnProcess(pp, cmd, argv, env):
            self.assertEqual([cmd, argv],
                             ['p4', [b'p4', b'login', b'-p']])
            pp.makeConnection(transport)
            self.assertEqual('pass\n', transport.msg)
            pp.outReceived('Enter password:\nTICKET_ID_GOES_HERE\n')
            so = error.ProcessDone(None)
            pp.processEnded(failure.Failure(so))
        self.patch(reactor, 'spawnProcess', spawnProcess)

        d = self.changesource.poll()

        def check_ticket_passwd(_):
            self.assertEqual(
                self.changesource._ticket_passwd, 'TICKET_ID_GOES_HERE')
        d.addCallback(check_ticket_passwd)
        return d

    def test_poll_split_file(self):
        """Make sure split file works on branch only changes"""
        self.attachChangeSource(
            P4Source(p4port=None, p4user=None,
                     p4base='//depot/myproject/',
                     split_file=get_simple_split))
        self.expectCommands(
            gpo.Expect(
                'p4', 'changes', '//depot/myproject/...@51,#head').stdout(third_p4changes),
        )
        self.add_p4_describe_result(5, p4change[5])

        self.changesource.last_change = 50
        d = self.changesource.poll()

        def check(res):
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
                'author': u'mpatel',
                'branch': u'branch_c',
                'category': None,
                'codebase': None,
                'comments': u'This is a multiline comment with tabs and spaces\n\nA list:\n  Item 1\n\tItem 2',
                'files': [u'branch_c_file'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': '5',
                'revlink': '',
                'src': None,
                'when_timestamp': datetime2epoch(when),
            }, {
                'author': u'mpatel',
                'branch': u'branch_b',
                'category': None,
                'codebase': None,
                'comments': u'This is a multiline comment with tabs and spaces\n\nA list:\n  Item 1\n\tItem 2',
                'files': [u'branch_b_file'],
                'project': '',
                'properties': {},
                'repository': '',
                'revision': '5',
                'revlink': '',
                'src': None,
                'when_timestamp': datetime2epoch(when),
            }], key=changeKey))
            self.assertEqual(self.changesource.last_change, 5)
            self.assertAllCommandsRan()
        d.addCallback(check)
        return d

    def test_server_tz(self):
        """Verify that the server_tz parameter is handled correctly"""
        self.attachChangeSource(
            P4Source(p4port=None, p4user=None,
                     p4base='//depot/myproject/',
                     split_file=get_simple_split,
                     server_tz="Europe/Berlin"))
        self.expectCommands(
            gpo.Expect(
                'p4', 'changes', '//depot/myproject/...@51,#head').stdout(third_p4changes),
        )
        self.add_p4_describe_result(5, p4change[5])

        self.changesource.last_change = 50
        d = self.changesource.poll()

        def check(res):
            # when_timestamp is converted from 21:55:39 Berlin time to UTC
            when_berlin = self.makeTime("2006/04/13 21:55:39")
            when_berlin = when_berlin.replace(
                tzinfo=dateutil.tz.gettz('Europe/Berlin'))
            when = datetime2epoch(when_berlin)

            self.assertEqual([ch['when_timestamp']
                              for ch in self.master.data.updates.changesAdded],
                             [when, when])
            self.assertAllCommandsRan()
        d.addCallback(check)
        return d


class TestSplit(unittest.TestCase):

    def test_get_simple_split(self):
        self.assertEqual(get_simple_split('foo/bar'), ('foo', 'bar'))
        self.assertEqual(get_simple_split('foo-bar'), (None, None))
        self.assertEqual(get_simple_split('/bar'), ('', 'bar'))
        self.assertEqual(get_simple_split('foo/'), ('foo', ''))
