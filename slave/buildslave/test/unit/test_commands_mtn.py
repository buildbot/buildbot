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
from buildslave.commands import mtn

class TestMonotone(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        repourl='mtn://code.monotone.ca/sandbox'
        branch='ca.monotone.sandbox.buildbot'
        
        self.patch_getCommand('mtn', 'path/to/mtn')
        self.clean_environ()
        self.make_command(mtn.Monotone, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl=repourl,
            branch=branch
        ))

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect(['path/to/mtn', 'db', 'info',
                    '--db', self.basedir + '/db.mtn'],
                   self.basedir,
                   keepStdout=True, sendRC=False, sendStderr=False,
                   usePTY=False, environ=exp_environ) + 0,
            Expect([ 'clobber', 'workdir' ],
                   self.basedir) + 0,
            Expect([ 'clobber', 'source' ],
                   self.basedir) + 0,
            Expect(['path/to/mtn', 'pull', repourl+"?"+branch,
                     '--db', self.basedir + '/db.mtn', '--ticker=none'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'checkout', self.basedir_source,
                    '--db', self.basedir + '/db.mtn',
                    '--branch', 'ca.monotone.sandbox.buildbot'],
                   self.basedir,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False,
                   environ=exp_environ) + 0,
            Expect(['path/to/mtn', 'automate', 'select', 'w:'],
                   self.basedir_source,
                   keepStdout=True, sendRC=False, timeout=120, usePTY=False)
                   + 0,
            Expect([ 'copy', 'source', 'workdir'],
                   self.basedir)
                   + 0,
            ]

        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, repourl+"?"+branch)
        return d

