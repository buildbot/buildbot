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

from __future__ import with_statement

import os
import string
import cStringIO
from twisted.trial import unittest
from buildbot.scripts import base
from buildbot.test.util import dirs, misc
from twisted.python import usage, runtime

class TestIBD(dirs.DirsMixin, misc.StdoutAssertionsMixin, unittest.TestCase):

    def setUp(self):
        self.setUpDirs('test')
        self.stdout = cStringIO.StringIO()
        self.setUpStdoutAssertions()

    def test_isBuildmasterDir_no_dir(self):
        self.assertFalse(base.isBuildmasterDir(os.path.abspath('test/nosuch')))
        self.assertInStdout('no buildbot.tac')

    def test_isBuildmasterDir_no_file(self):
        self.assertFalse(base.isBuildmasterDir(os.path.abspath('test')))
        self.assertInStdout('no buildbot.tac')

    def test_isBuildmasterDir_no_Application(self):
        with open(os.path.join('test', 'buildbot.tac'), 'w') as f:
            f.write("foo\nx = Application('buildslave')\nbar")
        self.assertFalse(base.isBuildmasterDir(os.path.abspath('test')))
        self.assertWasQuiet()

    def test_isBuildmasterDir_matches(self):
        with open(os.path.join('test', 'buildbot.tac'), 'w') as f:
            f.write("foo\nx = Application('buildmaster')\nbar")
        self.assertTrue(base.isBuildmasterDir(os.path.abspath('test')))
        self.assertWasQuiet()

class TestSubcommandOptions(unittest.TestCase):

    def fakeOptionsFile(self, **kwargs):
        self.patch(base.SubcommandOptions, 'loadOptionsFile',
                lambda self : kwargs.copy())

    def parse(self, cls, *args):
        self.opts = cls()
        self.opts.parseOptions(args)
        return self.opts

    class Bare(base.SubcommandOptions):
        optFlags = [ [ 'foo', 'f', 'Foo!' ] ]

    def test_bare_subclass(self):
        self.fakeOptionsFile()
        opts = self.parse(self.Bare, '-f')
        self.assertTrue(opts['foo'])

    class ParamsAndOptions(base.SubcommandOptions):
        optParameters = [ [ 'volume', 'v', '5', 'How Loud?' ] ]
        buildbotOptions = [ [ 'volcfg', 'volume' ] ]

    def test_buildbotOptions(self):
        self.fakeOptionsFile()
        opts = self.parse(self.ParamsAndOptions)
        self.assertEqual(opts['volume'], '5')

    def test_buildbotOptions_options(self):
        self.fakeOptionsFile(volcfg='3')
        opts = self.parse(self.ParamsAndOptions)
        self.assertEqual(opts['volume'], '3')

    def test_buildbotOptions_override(self):
        self.fakeOptionsFile(volcfg='3')
        opts = self.parse(self.ParamsAndOptions, '--volume', '7')
        self.assertEqual(opts['volume'], '7')

    class RequiredOptions(base.SubcommandOptions):
        optParameters = [ [ 'volume', 'v', None, 'How Loud?' ] ]
        requiredOptions = [ 'volume' ]

    def test_requiredOptions(self):
        self.fakeOptionsFile()
        self.assertRaises(usage.UsageError,
                lambda : self.parse(self.RequiredOptions))

class TestLoadOptionsFile(dirs.DirsMixin, misc.StdoutAssertionsMixin,
                          unittest.TestCase):

    def setUp(self):
        self.setUpDirs('test', 'home')
        self.opts = base.SubcommandOptions()
        self.dir = os.path.abspath('test')
        self.home = os.path.abspath('home')
        self.setUpStdoutAssertions()

    def tearDown(self):
        self.tearDownDirs()

    def do_loadOptionsFile(self, _here, exp):
        # only patch these os.path functions briefly, to
        # avoid breaking other parts of the test system
        patches = []

        if runtime.platformType == 'win32':
            from win32com.shell import shell
            patches.append(self.patch(shell, 'SHGetFolderPath',
                lambda *args : self.home))
        else:
            def expanduser(p):
                return p.replace('~/', self.home + '/')
            patches.append(self.patch(os.path, 'expanduser', expanduser))

        old_dirname = os.path.dirname
        def dirname(p):
            # bottom out at self.dir, rather than /
            if p == self.dir:
                return p
            return old_dirname(p)
        patches.append(self.patch(os.path, 'dirname', dirname))

        try:
            self.assertEqual(self.opts.loadOptionsFile(_here=_here), exp)
        finally:
            for p in patches:
                p.restore()

    def writeOptionsFile(self, dir, content, bbdir='.buildbot'):
        os.makedirs(os.path.join(dir, bbdir))
        with open(os.path.join(dir, bbdir, 'options'), 'w') as f:
            f.write(content)

    def test_loadOptionsFile_subdirs_not_found(self):
        subdir = os.path.join(self.dir, 'a', 'b')
        os.makedirs(subdir)
        self.do_loadOptionsFile(_here=subdir, exp={})

    def test_loadOptionsFile_subdirs_at_root(self):
        subdir = os.path.join(self.dir, 'a', 'b')
        os.makedirs(subdir)
        self.writeOptionsFile(self.dir, 'abc="def"')
        self.writeOptionsFile(self.home, 'abc=123') # not seen
        self.do_loadOptionsFile(_here=subdir, exp={'abc':'def'})

    def test_loadOptionsFile_subdirs_at_tip(self):
        subdir = os.path.join(self.dir, 'a', 'b')
        os.makedirs(subdir)
        self.writeOptionsFile(os.path.join(self.dir, 'a', 'b'), 'abc="def"')
        self.writeOptionsFile(self.dir, 'abc=123') # not seen
        self.do_loadOptionsFile(_here=subdir, exp={'abc':'def'})

    def test_loadOptionsFile_subdirs_at_homedir(self):
        subdir = os.path.join(self.dir, 'a', 'b')
        os.makedirs(subdir)
        # on windows, the subdir of the home (well, appdata) dir
        # is 'buildbot', not '.buildbot'
        self.writeOptionsFile(self.home, 'abc=123',
            'buildbot' if runtime.platformType == 'win32' else '.buildbot')
        self.do_loadOptionsFile(_here=subdir, exp={'abc':123})

    def test_loadOptionsFile_syntax_error(self):
        self.writeOptionsFile(self.dir, 'abc=abc')
        self.assertRaises(NameError, lambda :
            self.do_loadOptionsFile(_here=self.dir, exp={}))
        self.assertInStdout('error while reading')

    def test_loadOptionsFile_toomany(self):
        subdir = os.path.join(self.dir, *tuple(string.lowercase))
        os.makedirs(subdir)
        self.do_loadOptionsFile(_here=subdir, exp={})
        self.assertInStdout('infinite glories')

    # NOTE: testing the ownership check requires patching os.stat, which causes
    # other problems since it is so heavily used.
