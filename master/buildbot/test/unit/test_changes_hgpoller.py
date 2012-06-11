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
import shutil
from twisted.trial import unittest
from twisted.internet import defer
from exceptions import Exception
from buildbot.changes import hgpoller
from buildbot.test.util import changesource, gpo
from buildbot.test.fake.fakedb import FakeDBConnector
from buildbot.util import epoch2datetime

# Test that environment variables get propagated to subprocesses (See #2116)
os.environ['TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES'] = 'TRUE'

class TestHgPoller(gpo.GetProcessOutputMixin,
                   changesource.ChangeSourceMixin,
                   unittest.TestCase):

    def setUp(self):
        self.setUpGetProcessOutput()
        d = self.setUpChangeSource()
        self.remote_repo = 'ssh://example.com/foo/baz'
        def create_poller(_):
            self.poller = hgpoller.HgPoller(self.remote_repo,
                                            workdir='/some/dir')
            self.poller.master = self.master
        def create_db(_):
            db = self.master.db = FakeDBConnector(self)
            return db.setup()
        d.addCallback(create_poller)
        d.addCallback(create_db)
        return d

    def tearDown(self):
        self.tearDownGetProcessOutput()
        return self.tearDownChangeSource()

    def gpoFullcommandPattern(self, commandName, *expected_args):
        """Match if the command is commandName and arg list start as expected.

        This allows to test a bit more if expected GPO are issued, be it
        by obscure failures due to the result not being given.
        """
        def matchesSubcommand(bin, given_args, **kwargs):
            return bin == commandName and tuple(
                given_args[:len(expected_args)]) == expected_args
        return matchesSubcommand

    def test_describe(self):
        self.assertSubstring("HgPoller", self.poller.describe())

    def test_hgbin_default(self):
        self.assertEqual(self.poller.hgbin, "hg")

    def test_poll_initial(self):
        # Test that environment variables get propagated to subprocesses
        # (See #2116)
        os.putenv('TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES', 'TRUE')
        self.addGetProcessOutputExpectEnv(
            {'TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES': 'TRUE'})
        self.addGetProcessOutputAndValueExpectEnv(
            {'TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES': 'TRUE'})

        # patch out getProcessOutput and getProcessOutputAndValue for
        # expected hg calls
        self.addGetProcessOutputResult(
                self.gpoSubcommandPattern('hg', 'pull'), "any output")
        self.addGetProcessOutputResult(
                self.gpoFullcommandPattern('hg', 'heads', 'default'), '1')
        self.addGetProcessOutputResult(
                self.gpoFullcommandPattern('hg', 'log', '-b', 'default',
                                           '-r', '0:1'),
                os.linesep.join(['0:64a5dc2', '1:4423cdb']))
        self.addGetProcessOutputResult(
                self.gpoFullcommandPattern('hg', 'log', '-r', '64a5dc2'),
                os.linesep.join(['1273258009.0 -7200',
                                 'Joe Test <joetest@example.org>',
                                 'file1 file2',
                                 'Multi-line',
                                 'Comment for rev 0',
                                 '']))

        self.addGetProcessOutputResult(
                self.gpoFullcommandPattern('hg', 'log', '-r', '4423cdb'),
                os.linesep.join(['1273258100.0 -7200',
                                 'Bob Test <bobtest@example.org>',
                                 'file1 dir/file2',
                                 'This is rev 1',
                                 ]))

        # do the poll
        d = self.poller.poll()

        # check the results
        def check_changes(_):
            self.assertEqual(len(self.changes_added), 2)

            change = self.changes_added[0]
            self.assertEqual(change['revision'], '64a5dc2')
            self.assertEqual(change['author'],
                             'Joe Test <joetest@example.org>')
            self.assertEqual(change['when_timestamp'],
                             epoch2datetime(1273258009-7200)),
            self.assertEqual(change['files'], ['file1', 'file2'])
            self.assertEqual(change['src'], 'hg')
            self.assertEqual(change['branch'], 'default')
            self.assertEqual(change['comments'],
                             os.linesep.join(('Multi-line',
                                              'Comment for rev 0')))

            change = self.changes_added[1]
            self.assertEqual(change['revision'], '4423cdb')
            self.assertEqual(change['author'],
                             'Bob Test <bobtest@example.org>')
            self.assertEqual(change['when_timestamp'],
                             epoch2datetime(1273258100-7200)),
            self.assertEqual(change['files'], ['file1', 'dir/file2'])
            self.assertEqual(change['src'], 'hg')
            self.assertEqual(change['branch'], 'default')
            self.assertEqual(change['comments'], 'This is rev 1')

        d.addCallback(check_changes)

        def check_state(_):
            st = self.poller.getCurrentRev()
            def check(oid_rev):
                self.assertEqual(oid_rev[1], 1)
            st.addCallback(check)
        d.addCallback(check_state)

        return d
