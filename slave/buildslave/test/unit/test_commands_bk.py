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

from buildslave.commands import bk
from buildslave.test.fake.runprocess import Expect
from buildslave.test.util.sourcecommand import SourceCommandTestMixin


class TestBK(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.patch_getCommand('bk', 'path/to/bk')
        self.clean_environ()
        self.make_command(bk.BK, dict(
            workdir='workdir',
            mode='copy',
            revision='1.114',
            bkurl='http://bkdemo.bkbits.net/bk_demo1',
        ))

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect(['clobber', 'workdir'],
                   self.basedir)
            + 0,
            Expect(['clobber', 'source'],
                   self.basedir)
            + 0,
            Expect(['path/to/bk', 'clone', '-r1.114',
                    'http://bkdemo.bkbits.net/bk_demo1', 'source'],
                   self.basedir,
                   sendRC=False, timeout=120, usePTY=False)
            + 0,
            Expect(['path/to/bk', 'changes', '-r+', '-d:REV:'],
                   self.basedir_source,
                   sendRC=False, usePTY=False, timeout=120, sendStderr=False,
                   sendStdout=False, keepStdout=True, environ=exp_environ)
            + {'stdout': '1.114\n'}  # TODO: is this what BK outputs?
            + 0,
            Expect(['copy', 'source', 'workdir'],
                   self.basedir)
            + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        # TODO: why the extra quotes?
        d.addCallback(self.check_sourcedata, '"http://bkdemo.bkbits.net/bk_demo1\n"')
        return d
