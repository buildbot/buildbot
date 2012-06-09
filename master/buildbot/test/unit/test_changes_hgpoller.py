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
from buildbot.util import epoch2datetime

# Test that environment variables get propagated to subprocesses (See #2116)
os.environ['TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES'] = 'TRUE'

class HgOutputParsing(gpo.GetProcessOutputMixin, unittest.TestCase):
    """Test HgPoller methods for parsing hg output"""
    def setUp(self):
        self.poller = hgpoller.HgPoller('http://hg.example.com')
        self.setUpGetProcessOutput()

    def tearDown(self):
        self.tearDownGetProcessOutput()

    def _perform_hg_output_test(self, methodToTest,
                                 desiredGoodOutput, desiredGoodResult,
                                 emptyRaisesException=True):
        dummyRevStr = '12345abcde'

        # make this call to self.patch here so that we raise a SkipTest if it
        # is not supported
        self.addGetProcessOutputResult(self.gpoAnyPattern(), '')

        d = defer.succeed(None)
        def call_empty(_):
            # we should get an Exception with empty output from hg
            return methodToTest(dummyRevStr)
        d.addCallback(call_empty)

        def cb_empty(_):
            if emptyRaisesException:
                self.fail("getProcessOutput should have failed on empty output")
        def eb_empty(f):
            if not emptyRaisesException:
                self.fail("getProcessOutput should NOT have failed "
                          "on empty output")
        d.addCallbacks(cb_empty, eb_empty)

        # and the method shouldn't supress any exceptions
        def call_exception(_):
            # we should get an Exception with empty output from hg
            self.addGetProcessOutputResult(self.gpoAnyPattern(),
                    lambda b, a, **k: defer.fail(Exception('fake')))
            return methodToTest(dummyRevStr)
        d.addCallback(call_exception)

        def cb_exception(_):
            self.fail("getProcessOutput should have failed on empty output")
        def eb_exception(f):
            pass
        d.addCallbacks(cb_exception, eb_exception)

        # finally we should get what's expected from good output
        def call_desired(_):
            self.addGetProcessOutputResult(self.gpoAnyPattern(),
                desiredGoodOutput)
            return methodToTest(dummyRevStr)
        d.addCallback(call_desired)

        def cb_desired(r):
            self.assertEquals(r, desiredGoodResult)
        d.addCallback(cb_desired)

    def test_get_commit_author(self):
        authorStr = 'Joe Test <joetest@example.com>'
        return self._perform_hg_output_test(self.poller._get_commit_author,
                authorStr, authorStr)

    def test_get_commit_comments(self):
        commentStr = 'this is a commit message\n\nthat is multiline'
        return self._perform_hg_output_test(self.poller._get_commit_comments,
                commentStr, commentStr)

    def test_get_commit_files(self):
        filesStr = 'file1\nfile2'
        return self._perform_hg_output_test(self.poller._get_commit_files, filesStr,
                                      filesStr.split(), emptyRaisesException=False)

    def test_get_commit_timestamp(self):
        stampStr = '1273258009'
        return self._perform_hg_output_test(self.poller._get_commit_timestamp,
                stampStr, float(stampStr))

    # _get_changes is tested in TestHgPoller, below

class TestHgPoller(gpo.GetProcessOutputMixin,
                    changesource.ChangeSourceMixin,
                    unittest.TestCase):

    def setUp(self):
        self.setUpGetProcessOutput()
        d = self.setUpChangeSource()
        self.remote_repo = 'ssh://example.com/foo/baz'
        def create_poller(_):
            self.poller = hgpoller.HgPoller(self.remote_repo)
            self.poller.master = self.master
            os.mkdir(self.poller.workdir)
        d.addCallback(create_poller)
        return d

    def tearDown(self):
        shutil.rmtree(self.poller.workdir)
        self.tearDownGetProcessOutput()
        return self.tearDownChangeSource()

    def test_describe(self):
        self.assertSubstring("HgPoller", self.poller.describe())

    def test_hgbin_default(self):
        self.assertEqual(self.poller.hgbin, "hg")

    def test_poll(self):
        # Test that environment variables get propagated to subprocesses (See #2116)
        os.putenv('TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES', 'TRUE')
        self.addGetProcessOutputExpectEnv({'TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES': 'TRUE'})
        self.addGetProcessOutputAndValueExpectEnv({'TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES': 'TRUE'})

        # patch out getProcessOutput and getProcessOutputAndValue for the
        # benefit of the _get_changes method
        self.addGetProcessOutputResult(
                self.gpoSubcommandPattern('hg', 'pull'),# '-b', 'default',
                                          #self.remote_repo),
                "no interesting output")

        self.addGetProcessOutputResult(
                self.gpoSubcommandPattern('hg', 'log'), '1')

        self.addGetProcessOutputResult(
                self.gpoSubcommandPattern('hg', 'log'),
                '\n'.join([
                    '0:64a5dc2a4bd4f558b5dd193d47c83c7d7abc9a1a',
                    '1:4423cdbcbb89c14e50dd5f4152415afd686c5241']))

        # and patch out the _get_commit_foo methods which were already tested
        # above
        def timestamp(rev):
            return defer.succeed(1273258009.0)
        self.patch(self.poller, '_get_commit_timestamp', timestamp)
        def author(rev):
            return defer.succeed('by:' + rev[:8])
        self.patch(self.poller, '_get_commit_author', author)
        def files(rev):
            return defer.succeed(['/etc/' + rev[:3]])
        self.patch(self.poller, '_get_commit_files', files)
        def comments(rev):
            return defer.succeed('hello!')
        self.patch(self.poller, '_get_commit_comments', comments)

        # do the poll
        d = self.poller.poll()

        # check the results
        def check_changes(_):
            self.assertEqual(len(self.changes_added), 2)
            self.assertEqual(self.changes_added[0]['author'], 'by:0')
            self.assertEqual(self.changes_added[0]['when_timestamp'],
                                        epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[0]['comments'], 'hello!')
            self.assertEqual(self.changes_added[0]['branch'], 'default')
            self.assertEqual(self.changes_added[0]['files'], [ '/etc/0' ])
            self.assertEqual(self.changes_added[0]['src'], 'hg')

            self.assertEqual(self.changes_added[1]['author'], 'by:1')
            self.assertEqual(self.changes_added[1]['when_timestamp'],
                                        epoch2datetime(1273258009))
            self.assertEqual(self.changes_added[1]['comments'], 'hello!')
            self.assertEqual(self.changes_added[1]['files'], [ '/etc/1' ])
            self.assertEqual(self.changes_added[1]['src'], 'hg')
        d.addCallback(check_changes)

        return d
