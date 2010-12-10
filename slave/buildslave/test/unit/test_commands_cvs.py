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
from buildslave.commands import cvs

class TestCVS(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.patch_getCommand('cvs', 'path/to/cvs')
        self.clean_environ()
        self.make_command(cvs.CVS, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            cvsroot=':pserver:anoncvs@anoncvs.NetBSD.org:/cvsroot',
            cvsmodule='htdocs',
        ))

        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'clobber', 'source' ],
                self.basedir)
                + 0,
            Expect([ 'path/to/cvs', '-d', ':pserver:anoncvs@anoncvs.NetBSD.org:/cvsroot',
                     '-z3', 'checkout', '-d', 'source', 'htdocs' ],
                self.basedir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect([ 'copy', 'source', 'workdir'],
                self.basedir)
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata,
                ":pserver:anoncvs@anoncvs.NetBSD.org:/cvsroot\nhtdocs\nNone\n")
        return d

