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

from twisted.trial import unittest

from buildbot.revlinks import GithubRevlink
from buildbot.revlinks import GitwebMatch
from buildbot.revlinks import RevlinkMatch
from buildbot.revlinks import SourceforgeGitRevlink
from buildbot.revlinks import SourceforgeGitRevlink_AlluraPlatform
from buildbot.revlinks import default_revlink_matcher


class TestGithubRevlink(unittest.TestCase):
    revision = 'b6874701b54e0043a78882b020afc86033133f91'
    url = 'https://github.com/buildbot/buildbot/commit/b6874701b54e0043a78882b020afc86033133f91'

    def testHTTPS(self):
        self.assertEqual(GithubRevlink(self.revision, 'https://github.com/buildbot/buildbot.git'),
                         self.url)

    def testGIT(self):
        self.assertEqual(GithubRevlink(self.revision, 'git://github.com/buildbot/buildbot.git'),
                         self.url)

    def testSSH(self):
        self.assertEqual(GithubRevlink(self.revision, 'git@github.com:buildbot/buildbot.git'),
                         self.url)

    def testSSHuri(self):
        self.assertEqual(GithubRevlink(self.revision, 'ssh://git@github.com/buildbot/buildbot.git'),
                         self.url)


class TestSourceforgeGitRevlink(unittest.TestCase):
    revision = 'b99c89a2842d386accea8072ae5bb6e24aa7cf29'
    url = 'http://gemrb.git.sourceforge.net/git/gitweb.cgi?p=gemrb/gemrb;a=commit;h=b99c89a2842d386accea8072ae5bb6e24aa7cf29'

    def testGIT(self):
        self.assertEqual(SourceforgeGitRevlink(self.revision, 'git://gemrb.git.sourceforge.net/gitroot/gemrb/gemrb'),
                         self.url)

    def testSSH(self):
        self.assertEqual(SourceforgeGitRevlink(self.revision, 'somebody@gemrb.git.sourceforge.net:gitroot/gemrb/gemrb'),
                         self.url)

    def testSSHuri(self):
        self.assertEqual(SourceforgeGitRevlink(self.revision, 'ssh://somebody@gemrb.git.sourceforge.net/gitroot/gemrb/gemrb'),
                         self.url)


class TestSourceforgeGitRevlink_AlluraPlatform(unittest.TestCase):
    revision = '6f9b1470bae497c6ce47e4cf8c9195d864d2ba2f'
    url = 'https://sourceforge.net/p/klusters/klusters/ci/6f9b1470bae497c6ce47e4cf8c9195d864d2ba2f/'

    def testGIT(self):
        self.assertEqual(SourceforgeGitRevlink_AlluraPlatform(self.revision, 'git://git.code.sf.net/p/klusters/klusters'),
                         self.url)

    def testSSHuri(self):
        self.assertEqual(SourceforgeGitRevlink_AlluraPlatform(self.revision, 'ssh://somebody@git.code.sf.net/p/klusters/klusters'),
                         self.url)


class TestRevlinkMatch(unittest.TestCase):

    def testNotmuch(self):
        revision = 'f717d2ece1836c863f9cc02abd1ff2539307cd1d'
        matcher = RevlinkMatch(['git://notmuchmail.org/git/(.*)'],
                               r'http://git.notmuchmail.org/git/\1/commit/%s')
        self.assertEqual(matcher(revision, 'git://notmuchmail.org/git/notmuch'),
                         'http://git.notmuchmail.org/git/notmuch/commit/f717d2ece1836c863f9cc02abd1ff2539307cd1d')

    def testSingleString(self):
        revision = 'rev'
        matcher = RevlinkMatch('test', 'out%s')
        self.assertEqual(matcher(revision, 'test'), 'outrev')

    def testSingleUnicode(self):
        revision = 'rev'
        matcher = RevlinkMatch(u'test', 'out%s')
        self.assertEqual(matcher(revision, 'test'), 'outrev')

    def testTwoCaptureGroups(self):
        revision = 'rev'
        matcher = RevlinkMatch('([A-Z]*)Z([0-9]*)', r'\2-\1-%s')
        self.assertEqual(matcher(revision, 'ABCZ43'), '43-ABC-rev')


class TestGitwebMatch(unittest.TestCase):

    def testOrgmode(self):
        revision = '490d6ace10e0cfe74bab21c59e4b7bd6aa3c59b8'
        matcher = GitwebMatch(
            'git://orgmode.org/(?P<repo>.*)', 'http://orgmode.org/w/')
        self.assertEqual(matcher(revision, 'git://orgmode.org/org-mode.git'),
                         'http://orgmode.org/w/?p=org-mode.git;a=commit;h=490d6ace10e0cfe74bab21c59e4b7bd6aa3c59b8')


class TestDefaultRevlinkMultiPlexer(unittest.TestCase):
    revision = "0"

    def testAllRevlinkMatchers(self):
        # GithubRevlink
        self.assertTrue(default_revlink_matcher(
            self.revision, 'https://github.com/buildbot/buildbot.git'))
        # SourceforgeGitRevlink
        self.assertTrue(default_revlink_matcher(
            self.revision, 'git://gemrb.git.sourceforge.net/gitroot/gemrb/gemrb'))
        # SourceforgeGitRevlink_AlluraPlatform
        self.assertTrue(default_revlink_matcher(
            self.revision, 'git://git.code.sf.net/p/klusters/klusters'))
