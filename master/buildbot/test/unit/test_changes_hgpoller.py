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
import re
import subprocess

from twisted.internet import defer
from twisted.trial import unittest

from buildbot.changes import hgpoller
from buildbot.test.util import changesource
from buildbot.test.util import gpo

ENVIRON_2116_KEY = 'TEST_THAT_ENVIRONMENT_GETS_PASSED_TO_SUBPROCESSES'
LINESEP_BYTES = os.linesep.encode("ascii")
PATHSEP_BYTES = os.pathsep.encode("ascii")


class BaseTestHgPoller(gpo.GetProcessOutputMixin,
                       changesource.ChangeSourceMixin):

    usetimestamps = True

    def check_for_old_hgbin(self):
        resp = subprocess.Popen(['hg', '--version'], stdout=subprocess.PIPE)
        ver_str = resp.communicate()[0].decode().split("\n")[0]
        reg = re.compile(r'.*\((?P<version>version \d+\.\d+\.\d+)\)')
        reg_result = reg.search(ver_str)
        retval = False
        if reg_result:
            ver_result = reg_result.groups()[0].replace("version ", "")
            ver_result = ver_result.split(".")
            if int(ver_result[0]) < 2:
                retval = True
        return retval

    def setUp(self, remote_repo=None, branch='default', hgbin='hg', repo_ready=True,
              repo_dir='/some/dir'):
        # To test that environment variables get propagated to subprocesses
        # (See #2116)
        os.environ[ENVIRON_2116_KEY] = 'TRUE'
        self.setUpGetProcessOutput()
        self.hgbin = hgbin
        d = self.setUpChangeSource()
        self.remote_repo = remote_repo
        self.branch = branch
        self.repo_dir = repo_dir
        self.repo_ready = repo_ready

        def _isRepositoryReady():
            return self.repo_ready

        def create_poller(_):
            self.poller = hgpoller.HgPoller(self.remote_repo,
                                            hgbin=self.hgbin,
                                            usetimestamps=self.usetimestamps,
                                            workdir='/some/dir')
            self.poller.setServiceParent(self.master)
            self.poller._isRepositoryReady = _isRepositoryReady

        def create_db(_):
            return self.master.db.setup()

        d.addCallback(create_poller)
        d.addCallback(create_db)
        return d

    def tearDown(self):
        del os.environ[ENVIRON_2116_KEY]
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

    def test_name(self):
        self.assertEqual(
            "%s[%s]" % (self.remote_repo, self.branch), self.poller.name)

        # and one with explicit name...
        other = hgpoller.HgPoller(
            self.remote_repo, name="MyName", workdir='/some/dir')
        self.assertEqual("MyName", other.name)

    def test_hgbin_default(self):
        self.assertEqual(self.poller.hgbin, self.hgbin)

    @defer.inlineCallbacks
    def test_poll_initial(self):
        if self.check_for_old_hgbin():
            raise unittest.SkipTest("old hg binary found. Skipping test")
        self.repo_ready = False
        # Test that environment variables get propagated to subprocesses
        # (See #2116)
        expected_env = {ENVIRON_2116_KEY: 'TRUE'}
        self.addGetProcessOutputExpectEnv(expected_env)
        self.expectCommands(
            gpo.Expect(self.hgbin, 'init', self.repo_dir),
            gpo.Expect(self.hgbin, 'pull', '-b', 'default',
                       self.remote_repo)
            .path(self.repo_dir),
            gpo.Expect(
                self.hgbin, 'heads', 'default', '--template={rev}' + os.linesep)
            .path(self.repo_dir).stdout(b"73591"),
            gpo.Expect(self.hgbin, 'log', '-b', 'default', '-r', '73591:73591',  # only fetches that head
                       '--template={rev}:{node}\\n')
            .path(self.repo_dir).stdout(LINESEP_BYTES.join([b'73591:4423cdb'])),
            gpo.Expect(self.hgbin, 'log', '-r', '4423cdb',
                       '--template={date|hgdate}' + os.linesep + '{author}' + os.linesep + "{files % '{file}" + os.pathsep + "'}" + os.linesep + '{desc|strip}')
            .path(self.repo_dir).stdout(LINESEP_BYTES.join([
                b'1273258100.0 -7200',
                b'Bob Test <bobtest@example.org>',
                b'file1 with spaces' + PATHSEP_BYTES +
                os.path.join(b'dir with spaces', b'file2') + PATHSEP_BYTES,
                b'This is rev 73591',
                b''])),
        )

        # do the poll
        yield self.poller.poll()

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)

        change = self.master.data.updates.changesAdded[0]
        self.assertEqual(change['revision'], '4423cdb')
        self.assertEqual(change['author'],
                         'Bob Test <bobtest@example.org>')
        if self.usetimestamps:
            self.assertEqual(change['when_timestamp'], 1273258100)
        else:
            self.assertEqual(change['when_timestamp'], None)
        self.assertEqual(
            change['files'], ['file1 with spaces', os.path.join('dir with spaces', 'file2')])
        self.assertEqual(change['src'], 'hg')
        self.assertEqual(change['branch'], 'default')
        self.assertEqual(change['comments'], 'This is rev 73591')

        yield self.check_current_rev(73591)

    def check_current_rev(self, wished):
        def check_on_rev(_):
            d = self.poller._getCurrentRev()
            d.addCallback(lambda oid_rev: self.assertEqual(oid_rev[1], wished))
        return check_on_rev

    @defer.inlineCallbacks
    def test_poll_several_heads(self):
        if self.check_for_old_hgbin():
            raise unittest.SkipTest("old hg binary found. Skipping test")

        # If there are several heads on the named branch, the poller mustn't
        # climb (good enough for now, ideally it should even go to the common
        # ancestor)
        self.expectCommands(
            gpo.Expect(self.hgbin, 'init', self.repo_dir),
            gpo.Expect(self.hgbin, 'pull', '-b', 'default',
                       self.remote_repo)
            .path(self.repo_dir),
            gpo.Expect(
                self.hgbin, 'heads', 'default', '--template={rev}' + os.linesep)
            .path(self.repo_dir).stdout(b'5' + LINESEP_BYTES + b'6' + LINESEP_BYTES)
        )

        yield self.poller._setCurrentRev(3)

        # do the poll: we must stay at rev 3
        yield self.poller.poll()
        yield self.check_current_rev(3)

    @defer.inlineCallbacks
    def test_poll_regular(self):
        if self.check_for_old_hgbin():
            raise unittest.SkipTest("old hg binary found. Skipping test")

        # normal operation. There's a previous revision, we get a new one.
        self.expectCommands(
            gpo.Expect(self.hgbin, 'init', self.repo_dir),
            gpo.Expect(self.hgbin, 'pull', '-b', 'default',
                       self.remote_repo)
            .path(self.repo_dir),
            gpo.Expect(
                self.hgbin, 'heads', 'default', '--template={rev}' + os.linesep)
            .path(self.repo_dir).stdout(b'5' + LINESEP_BYTES),
            gpo.Expect(self.hgbin, 'log', '-b', 'default', '-r', '5:5',
                       '--template={rev}:{node}\\n')
            .path(self.repo_dir).stdout(b'5:784bd' + LINESEP_BYTES),
            gpo.Expect(self.hgbin, 'log', '-r', '784bd',
                       '--template={date|hgdate}' + os.linesep + '{author}' + os.linesep + "{files % '{file}" + os.pathsep + "'}" + os.linesep + '{desc|strip}')
            .path(self.repo_dir).stdout(LINESEP_BYTES.join([
                b'1273258009.0 -7200',
                b'Joe Test <joetest@example.org>',
                b'file1 file2',
                b'Comment for rev 5',
                b''])),
        )

        yield self.poller._setCurrentRev(4)

        yield self.poller.poll()
        yield self.check_current_rev(5)

        self.assertEqual(len(self.master.data.updates.changesAdded), 1)
        change = self.master.data.updates.changesAdded[0]
        self.assertEqual(change['revision'], u'784bd')
        self.assertEqual(change['comments'], u'Comment for rev 5')


class TestHgPoller(BaseTestHgPoller, unittest.TestCase):
    usetimestamps = True

    def setUp(self):
        return BaseTestHgPoller.setUp(self, remote_repo='ssh://example.com/foo/baz')


class HgPollerNoTimestamp(TestHgPoller):
    """ Test HgPoller() without parsing revision commit timestamp """

    usetimestamps = False


class TestOldHgPoller(BaseTestHgPoller, unittest.TestCase):
    usetimestamps = True

    def setUp(self):
        return BaseTestHgPoller.setUp(self, remote_repo='ssh://example.com/foo/bar',
                                      hgbin='/usr/bin/hg')


class OldHgPollerNoTimestamp(TestHgPoller):
    """ Test HgPoller() without parsing revision commit timestamp """

    usetimestamps = False
