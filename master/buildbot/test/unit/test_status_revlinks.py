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

import mock
from twisted.trial import unittest
from buildbot.status.revlinks import RevlinkMatch, GithubRevlink, SourceforgeGitRevlink

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
