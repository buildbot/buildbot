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

from twisted.trial import unittest

from buildslave.test.fake.runprocess import Expect
from buildslave.test.util.sourcecommand import SourceCommandTestMixin
from buildslave.commands import darcs

class TestDarcs(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.patch_getCommand('darcs', 'path/to/darcs')
        self.clean_environ()
        self.make_command(darcs.Darcs, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl='http://darcs.net',
        ))

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'clobber', 'source' ],
                self.basedir)
                + 0,
            Expect([ 'path/to/darcs', 'get', '--verbose', '--partial', '--repo-name',
                     'source', 'http://darcs.net'],
                self.basedir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'path/to/darcs', 'changes', '--context' ],
                self.basedir_source,
                sendRC=False, timeout=120, usePTY=False, keepStdout=True,
                environ=exp_environ, sendStderr=False, sendStdout=False)
                + { 'stdout' : example_changes }
                + 0,
            Expect([ 'copy', 'source', 'workdir'],
                self.basedir)
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "http://darcs.net\n")
        return d

example_changes = """\

Context:

[Resolve issue1874: recognise network tests on cabal test command line.
Eric Kow <kowey@darcs.net>**20100611102251
 Ignore-this: 59a455ef26b5df9a3bdd356e1e37854e
] 

[haddocks for SelectChanges
Florent Becker <florent.becker@ens-lyon.org>**20100610140023
 Ignore-this: c4203f746fc6278dc5290332e3625283
] 

[better message when skipping already decided patches
Florent Becker <florent.becker@ens-lyon.org>**20100531065630
 Ignore-this: 426675973555e75086781f0c54fbf925
] 

[Accept issue1871: darcs record . failure for changes in subdir.
Eric Kow <kowey@darcs.net>**20100609145047
 Ignore-this: dd942b980dd3006bfa5d176ec5cfdf99
] 

[Extend the issue1014 test to check that named patches are not duplicated.
Petr Rockai <me@mornfall.net>**20100607185041
 Ignore-this: 383ff17461076a798193b6c0c2427bba
] 

[Haddock merge2FL and fastRemoveFL in Patch.Depends.
Petr Rockai <me@mornfall.net>**20100607184849
 Ignore-this: cd6e79c4e404820d4f0ae94a53aed8c1
] 

[Limit index updates to relevant subtree in a few cases.
Petr Rockai <me@mornfall.net>**20100509102248
 Ignore-this: fea041133d039cecead73935f0cd6762
] 

[Fix a bunch of "unused" warnings.
Petr Rockai <me@mornfall.net>**20100607194111
 Ignore-this: 1fec82080eca9c3f10b690ee0ef81e34
] 

[Shorten issue1210 test name.
Eric Kow <kowey@darcs.net>**20100608090708
 Ignore-this: 57ff2a1cbb9795f80ae3d81e19717a9e
] 

[Add test for issue1210: global cache gets recorded in _darcs/prefs/sources
builes.adolfo@googlemail.com**20100608010902
 Ignore-this: bc02ada910927be93dd4a5cc9826d20d
] 

[Fix typo in the BSD version of date arithmetic (testsuite).
Petr Rockai <me@mornfall.net>**20100608062802
 Ignore-this: fdfb7aef46966a18edc2f7e93c0118f0
] 

[Let's try to work with BSD date as well.
Petr Rockai <me@mornfall.net>**20100608061631
 Ignore-this: 628e6f15e8f8d6801a3f1dd6c8605e17
] 

[Fix a race condition in the match-date test.
Petr Rockai <me@mornfall.net>**20100607223257
 Ignore-this: 4c6452bfdee6c03eb95abcd646add90f
] 
"""
