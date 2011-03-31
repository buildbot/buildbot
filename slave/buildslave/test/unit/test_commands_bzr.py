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

import textwrap

from twisted.trial import unittest

from buildslave.test.fake.runprocess import Expect
from buildslave.test.util.sourcecommand import SourceCommandTestMixin
from buildslave.commands import bzr

class TestBzr(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.patch_getCommand('bzr', 'path/to/bzr')
        self.clean_environ()
        self.make_command(bzr.Bzr, dict(
            workdir='workdir',
            mode='copy',
            revision='12',
            repourl='http://bazaar.launchpad.net/~bzr/bzr-gtk/trunk',
        ))

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        verinfo = textwrap.dedent("""\
            revision-id: pqm@pqm.ubuntu.com-20071211175118-s94sizduj201hrs5
            date: 2007-12-11 17:51:18 +0000
            build-date: 2007-12-13 13:14:51 +1000
            revno: 3104
            branch-nick: bzr.dev
        """)
        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'clobber', 'source' ],
                self.basedir)
                + 0,
                Expect([ 'path/to/bzr', 'checkout', '--revision', '12',
                         'http://bazaar.launchpad.net/~bzr/bzr-gtk/trunk', 'source' ],
                self.basedir,
                sendRC=False, timeout=120, usePTY=False)
                + 0,
            Expect(['path/to/bzr', 'version-info'],
                self.basedir_source,
                sendRC=False, usePTY=False, keepStdout=True,
                environ=exp_environ, sendStderr=False, sendStdout=False)
                + { 'stdout' : verinfo }
                + 0,
            Expect([ 'copy', 'source', 'workdir'],
                self.basedir)
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "http://bazaar.launchpad.net/~bzr/bzr-gtk/trunk\n")
        return d

