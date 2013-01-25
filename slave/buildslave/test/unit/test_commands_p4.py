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
from buildslave.commands import p4
from buildslave.util import Obfuscated

class TestP4(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.patch_getCommand('p4', 'path/to/p4')
        self.clean_environ()
        self.make_command(p4.P4, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            p4port='p4dserv:1666',
            p4client='buildbot_test_10',
            p4user='jimmy',
            p4passwd='hushnow',
            p4base='//mydepot/myproj/',
            branch='mytrunk',
            p4extra_views=[],
        ))

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        # can't use textwrap.dedent here, because in 2.4 it converts \t to 8x' '
        client_spec = """\
Client: buildbot_test_10

Owner: jimmy

Description:
\tCreated by jimmy

Root:\t%s

Options:\tallwrite rmdir

LineEnd:\tlocal

View:
\t//mydepot/myproj/mytrunk/... //buildbot_test_10/source/...
""" % self.basedir
        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'clobber', 'source' ],
                self.basedir)
                + 0,
            Expect(['p4', '-p', 'p4dserv:1666', '-u', 'jimmy', '-P', 
                    Obfuscated('hushnow', 'XXXXXXXX'), 'client', '-i'],
                self.basedir,
                                                # TODO: empty env?
                sendRC=False, timeout=120, usePTY=False, environ={},
                initialStdin=client_spec)
                + 0,
            Expect(['p4', '-p', 'p4dserv:1666', '-u', 'jimmy', '-P',
                    Obfuscated('hushnow', 'XXXXXXXX'), '-c', 'buildbot_test_10', 'sync', '-f'],
                self.basedir,
                                                # TODO: empty env?
                sendRC=False, timeout=120, usePTY=False, environ={})
                + 0,
            Expect(['p4', '-p', 'p4dserv:1666', '-u', 'jimmy', '-P',
                    Obfuscated('hushnow', 'XXXXXXXX'), '-c', 'buildbot_test_10', 'changes',
                    '-s', 'submitted', '-m', '1', '#have'],
                self.basedir,
                sendRC=False, timeout=120, usePTY=False, environ=exp_environ,
                keepStdout=True)
                + { 'stdout' : 'Change 28147 on 2008/04/07 by p4user@hostname\n' }
                + 0,
            Expect([ 'copy', 'source', 'workdir'],
                self.basedir)
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "['p4dserv:1666', 'buildbot_test_10', " +
               "'//mydepot/myproj/', 'mytrunk', [], None, %s, 'copy', 'workdir']"
               % `self.basedir`)
        return d

    def test_simple_unicode_args(self):
        self.patch_getCommand('p4', 'path/to/p4')
        self.clean_environ()
        self.make_command(p4.P4, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            p4port=u'p4dserv:1666\N{SNOWMAN}',
            p4client=u'buildbot_test_10\N{SNOWMAN}',
            p4user='jimmy',
            p4passwd='hushnow',
            p4base=u'//mydepot/myproj/\N{SNOWMAN}',
            branch=u'mytrunk\N{SNOWMAN}',
            p4extra_views=[],
        ))

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        # can't use textwrap.dedent here, because in 2.4 it converts \t to 8x' '
        client_spec = """\
Client: buildbot_test_10

Owner: jimmy

Description:
\tCreated by jimmy

Root:\t%s

Options:\tallwrite rmdir

LineEnd:\tlocal

View:
\t//mydepot/myproj/mytrunk/... //buildbot_test_10/source/...
""" % self.basedir
        expects = [
            Expect([ 'clobber', 'workdir' ],
                self.basedir)
                + 0,
            Expect([ 'clobber', 'source' ],
                self.basedir)
                + 0,
            Expect(['p4', '-p', u'p4dserv:1666\N{SNOWMAN}', '-u', 'jimmy', '-P', 
                    Obfuscated('hushnow', 'XXXXXXXX'), 'client', '-i'],
                self.basedir,
                                                # TODO: empty env?
                sendRC=False, timeout=120, usePTY=False, environ={},
                initialStdin=client_spec)
                + 0,
            Expect(['p4', '-p', u'p4dserv:1666\N{SNOWMAN}', '-u', 'jimmy', '-P',
                    Obfuscated('hushnow', 'XXXXXXXX'), '-c',
                    u'buildbot_test_10\N{SNOWMAN}', 'sync', '-f'],
                self.basedir,
                                                # TODO: empty env?
                sendRC=False, timeout=120, usePTY=False, environ={})
                + 0,
            Expect(['p4', '-p', u'p4dserv:1666\N{SNOWMAN}', '-u', 'jimmy', '-P',
                    Obfuscated('hushnow', 'XXXXXXXX'), '-c',
                    u'buildbot_test_10\N{SNOWMAN}', 'changes',
                    '-s', 'submitted', '-m', '1', '#have'],
                self.basedir,
                sendRC=False, timeout=120, usePTY=False, environ=exp_environ,
                keepStdout=True)
                + { 'stdout' : 'Change 28147 on 2008/04/07 by p4user@hostname\n' }
                + 0,
            Expect([ 'copy', 'source', 'workdir'],
                self.basedir)
                + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata,
                "['p4dserv:1666\\xe2\\x98\\x83', "
                "'buildbot_test_10\\xe2\\x98\\x83', "
                "'//mydepot/myproj/\\xe2\\x98\\x83', "
                "'mytrunk\\xe2\\x98\\x83', [], None, %s, 'copy', "
                "'workdir']"
               % `self.basedir`)
        return d

