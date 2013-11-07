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

from buildslave.commands import hg
from buildslave.test.fake.runprocess import Expect
from buildslave.test.util.sourcecommand import SourceCommandTestMixin


class TestMercurial(SourceCommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def patch_sourcedirIsUpdateable(self, result):
        self.cmd.sourcedirIsUpdateable = lambda: result

    def test_simple(self):
        self.patch_getCommand('hg', 'path/to/hg')
        self.clean_environ()
        self.make_command(hg.Mercurial, dict(
            workdir='workdir',
            mode='copy',
            revision=None,
            repourl='http://bitbucket.org/nicolas17/pyboinc',
        ))

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect(['clobber', 'workdir'],
                   self.basedir)
            + 0,
            Expect(['clobber', 'source'],
                   self.basedir)
            + 0,
            Expect(['path/to/hg', 'clone', '--verbose', '--noupdate',
                    'http://bitbucket.org/nicolas17/pyboinc', 'source'],
                   self.basedir,
                   sendRC=False, timeout=120, usePTY=False)
            + 0,
            Expect(['path/to/hg', 'identify', '--num', '--branch'],
                   self.basedir_source,
                   sendRC=False, timeout=120, usePTY=False, keepStdout=True,
                   keepStderr=True)
            + {'stdout': '-1 default\n'}
            + 0,
            Expect(['path/to/hg', 'paths', 'default'],
                   self.basedir_source,
                   sendRC=False, timeout=120, usePTY=False, keepStdout=True,
                   keepStderr=True)
            + {'stdout': 'http://bitbucket.org/nicolas17/pyboinc\n'}
            + 0,
            Expect(['path/to/hg', 'update', '--clean', '--repository',
                    'source', '--rev', 'default'],
                   self.basedir,
                   sendRC=False, timeout=120, usePTY=False)
            + 0,
            Expect(['path/to/hg', 'parents', '--template', '{node}\\n'],
                   self.basedir_source,
                   sendRC=False, timeout=120, usePTY=False, environ=exp_environ,
                   keepStdout=True)
            + {'stdout': 'b7ddc0b638fa11cdac7c0345c40c6f76d8a7166d'}
            + 0,
            Expect(['copy', 'source', 'workdir'],
                   self.basedir)
            + 0,
        ]
        self.patch_runprocess(*expects)

        d = self.run_command()
        d.addCallback(self.check_sourcedata, "http://bitbucket.org/nicolas17/pyboinc\n")
        return d

    def test_update_existing(self):
        self.patch_getCommand('hg', 'path/to/hg')
        self.clean_environ()
        self.make_command(hg.Mercurial, dict(
            workdir='workdir',
            mode='update',
            revision=None,
            repourl='http://bitbucket.org/nicolas17/pyboinc',
        ),
            initial_sourcedata="http://bitbucket.org/nicolas17/pyboinc\n",
        )
        self.patch_sourcedirIsUpdateable(True)

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect(['path/to/hg', 'pull', '--verbose', 'http://bitbucket.org/nicolas17/pyboinc'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, keepStdout=True, usePTY=False)
            + 0,
            Expect(['path/to/hg', 'identify', '--num', '--branch'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, usePTY=False, keepStdout=True,
                   keepStderr=True)
            + {'stdout': '-1 default\n'}
            + 0,
            Expect(['path/to/hg', 'paths', 'default'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, usePTY=False, keepStdout=True,
                   keepStderr=True)
            + {'stdout': 'http://bitbucket.org/nicolas17/pyboinc\n'}
            + 0,
            Expect(['path/to/hg', 'update', '--clean', '--repository',
                    'workdir', '--rev', 'default'],
                   self.basedir,
                   sendRC=False, timeout=120, usePTY=False)
            + 0,
            Expect(['path/to/hg', 'parents', '--template', '{node}\\n'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, usePTY=False, environ=exp_environ,
                   keepStdout=True)
            + {'stdout': 'b7ddc0b638fa11cdac7c0345c40c6f76d8a7166d'}
            + 0,
        ]
        self.patch_runprocess(*expects)
        d = self.run_command()
        d.addCallback(self.check_sourcedata, "http://bitbucket.org/nicolas17/pyboinc\n")
        return d

    def test_update_existing_change_branch(self):
        self.patch_getCommand('hg', 'path/to/hg')
        self.clean_environ()
        self.make_command(hg.Mercurial, dict(
            workdir='workdir',
            mode='update',
            revision=None,
            branch='stable',
            repourl='http://bitbucket.org/nicolas17/pyboinc',
            clobberOnBranchChange=True,
        ),
            initial_sourcedata="http://bitbucket.org/nicolas17/pyboinc\n",
        )
        self.patch_sourcedirIsUpdateable(True)

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect(['path/to/hg', 'pull', '--verbose', 'http://bitbucket.org/nicolas17/pyboinc'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, keepStdout=True, usePTY=False)
            + 0,
            Expect(['path/to/hg', 'identify', '--num', '--branch'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, usePTY=False, keepStdout=True,
                   keepStderr=True)
            + {'stdout': '1 default\n'}
            + 0,
            Expect(['path/to/hg', 'paths', 'default'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, usePTY=False, keepStdout=True,
                   keepStderr=True)
            + {'stdout': 'http://bitbucket.org/nicolas17/pyboinc\n'}
            + 0,
            Expect(['path/to/hg', 'purge', '--all'],
                   self.basedir_workdir,
                   keepStdout=True, keepStderr=True, usePTY=False)
            + 0,
            Expect(['path/to/hg', 'update', '--clean', '--repository',
                    'workdir', '--rev', 'stable'],
                   self.basedir,
                   sendRC=False, timeout=120, usePTY=False)
            + 0,
            Expect(['path/to/hg', 'parents', '--template', '{node}\\n'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, usePTY=False, environ=exp_environ,
                   keepStdout=True)
            + {'stdout': 'b7ddc0b638fa11cdac7c0345c40c6f76d8a7166d'}
            + 0,

        ]
        self.patch_runprocess(*expects)
        d = self.run_command()
        d.addCallback(self.check_sourcedata, "http://bitbucket.org/nicolas17/pyboinc\n")
        return d

    def test_update_handle_emptyupdate(self):
        self.patch_getCommand('hg', 'path/to/hg')
        self.clean_environ()
        self.make_command(hg.Mercurial, dict(
            workdir='workdir',
            mode='update',
            revision=None,
            repourl='http://bitbucket.org/nicolas17/pyboinc',
        ),
            initial_sourcedata="http://bitbucket.org/nicolas17/pyboinc\n",
        )
        self.patch_sourcedirIsUpdateable(True)

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect(['path/to/hg', 'pull', '--verbose', 'http://bitbucket.org/nicolas17/pyboinc'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, keepStdout=True, usePTY=False)
            + 1,
            Expect(['clobber', 'workdir'],
                   self.basedir)
            + 0,
            Expect(['path/to/hg', 'clone', '--verbose', '--noupdate',
                    'http://bitbucket.org/nicolas17/pyboinc', 'workdir'],
                   self.basedir,
                   sendRC=False, timeout=120, usePTY=False)
            + 0,
            Expect(['path/to/hg', 'identify', '--num', '--branch'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, usePTY=False, keepStdout=True,
                   keepStderr=True)
            + {'stdout': '-1 default\n'}
            + 0,
            Expect(['path/to/hg', 'paths', 'default'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, usePTY=False, keepStdout=True,
                   keepStderr=True)
            + {'stdout': 'http://bitbucket.org/nicolas17/pyboinc\n'}
            + 0,
            Expect(['path/to/hg', 'update', '--clean', '--repository',
                    'workdir', '--rev', 'default'],
                   self.basedir,
                   sendRC=False, timeout=120, usePTY=False)
            + 0,
            Expect(['path/to/hg', 'parents', '--template', '{node}\\n'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, usePTY=False, environ=exp_environ,
                   keepStdout=True)
            + {'stdout': 'b7ddc0b638fa11cdac7c0345c40c6f76d8a7166d'}
            + 0,
        ]
        self.patch_runprocess(*expects)
        d = self.run_command()
        d.addCallback(self.check_sourcedata, "http://bitbucket.org/nicolas17/pyboinc\n")
        return d

    def test_update_existing_change_branch_purge_fail(self):
        self.patch_getCommand('hg', 'path/to/hg')
        self.clean_environ()
        self.make_command(hg.Mercurial, dict(
            workdir='workdir',
            mode='update',
            revision="abcdef01",
            branch='stable',
            repourl='http://bitbucket.org/nicolas17/pyboinc',
            clobberOnBranchChange=True,
        ),
            initial_sourcedata="http://bitbucket.org/nicolas17/pyboinc\n",
        )
        self.patch_sourcedirIsUpdateable(True)

        exp_environ = dict(PWD='.', LC_MESSAGES='C')
        expects = [
            Expect(['path/to/hg', 'pull', '--verbose', 'http://bitbucket.org/nicolas17/pyboinc'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, keepStdout=True, usePTY=False)
            + 0,
            Expect(['path/to/hg', 'identify', '--num', '--branch'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, usePTY=False, keepStdout=True,
                   keepStderr=True)
            + {'stdout': '1 default\n'}
            + 0,
            Expect(['path/to/hg', 'paths', 'default'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, usePTY=False, keepStdout=True,
                   keepStderr=True)
            + {'stdout': 'http://bitbucket.org/nicolas17/pyboinc\n'}
            + 0,
            Expect(['path/to/hg', 'purge', '--all'],
                   self.basedir_workdir,
                   keepStdout=True, keepStderr=True, usePTY=False)
            + 1,
            Expect(['clobber', 'workdir'],
                   self.basedir)
            + 0,
            Expect(['path/to/hg', 'clone', '--verbose', '--noupdate',
                    'http://bitbucket.org/nicolas17/pyboinc', 'workdir'],
                   self.basedir,
                   sendRC=False, timeout=120, usePTY=False)
            + 0,
            Expect(['path/to/hg', 'identify', '--num', '--branch'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, usePTY=False, keepStdout=True,
                   keepStderr=True)
            + {'stdout': '-1 default\n'}
            + 0,
            Expect(['path/to/hg', 'paths', 'default'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, usePTY=False, keepStdout=True,
                   keepStderr=True)
            + {'stdout': 'http://bitbucket.org/nicolas17/pyboinc\n'}
            + 0,
            Expect(['path/to/hg', 'update', '--clean', '--repository',
                    'workdir', '--rev', 'abcdef01'],
                   self.basedir,
                   sendRC=False, timeout=120, usePTY=False)
            + 0,
            Expect(['path/to/hg', 'update', '--clean', '--repository',
                    'workdir', '--rev', 'abcdef01'],
                   self.basedir,
                   sendRC=False, timeout=120, usePTY=False)
            + 0,
            Expect(['path/to/hg', 'parents', '--template', '{node}\\n'],
                   self.basedir_workdir,
                   sendRC=False, timeout=120, usePTY=False, environ=exp_environ,
                   keepStdout=True)
            + {'stdout': 'b7ddc0b638fa11cdac7c0345c40c6f76d8a7166d'}
            + 0,

        ]
        self.patch_runprocess(*expects)
        d = self.run_command()
        d.addCallback(self.check_sourcedata, "http://bitbucket.org/nicolas17/pyboinc\n")
        return d
