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

import os
import shutil

from os import errno

from twisted.trial import unittest

from buildslave.commands import fs
from buildslave.commands import utils
from buildslave.test.util import compat
from buildslave.test.util.command import CommandTestMixin
from twisted.internet import defer


class TestRemoveDirectory(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_simple(self):
        self.make_command(fs.RemoveDirectory, dict(
            dir='workdir',
        ), True)

        yield self.run_command()

        self.assertFalse(os.path.exists(
            os.path.abspath(os.path.join(self.basedir, 'workdir'))))
        self.assertIn({'rc': 0},
                      self.get_updates(),
                      self.builder.show())

    # we only use rmdirRecursive on windows
    @compat.skipUnlessPlatformIs("win32")
    @defer.inlineCallbacks
    def test_simple_exception(self):

        def fail(dir):
            raise RuntimeError("oh noes")
        self.patch(utils, 'rmdirRecursive', fail)

        self.make_command(fs.RemoveDirectory, dict(
            dir='workdir',
        ), True)

        yield self.run_command()

        self.assertIn({'rc': -1}, self.get_updates(), self.builder.show())

    @defer.inlineCallbacks
    def test_multiple_dirs(self):
        self.make_command(fs.RemoveDirectory, dict(
            dir=['workdir', 'sourcedir'],
        ), True)

        yield self.run_command()

        for dirname in ['workdir', 'sourcedir']:
            self.assertFalse(os.path.exists(
                os.path.abspath(os.path.join(self.basedir, dirname))))

        self.assertIn({'rc': 0},
                      self.get_updates(),
                      self.builder.show())


class TestCopyDirectory(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_simple(self):
        self.make_command(fs.CopyDirectory, dict(
            fromdir='workdir',
            todir='copy',
        ), True)

        yield self.run_command()

        self.assertTrue(os.path.exists(
            os.path.abspath(os.path.join(self.basedir, 'copy'))))
        # this may ignore a 'header' : '..', which is OK
        self.assertIn({'rc': 0},
                      self.get_updates(),
                      self.builder.show())

    # we only use rmdirRecursive on windows
    @compat.skipUnlessPlatformIs("win32")
    @defer.inlineCallbacks
    def test_simple_exception(self):

        def fail(src, dest):
            raise RuntimeError("oh noes")
        self.patch(shutil, 'copytree', fail)
        self.make_command(fs.CopyDirectory, dict(
            fromdir='workdir',
            todir='copy',
        ), True)

        yield self.run_command()

        self.assertIn({'rc': -1},
                      self.get_updates(),
                      self.builder.show())


class TestMakeDirectory(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_simple(self):
        self.make_command(fs.MakeDirectory, dict(
            dir='test-dir',
        ), True)

        yield self.run_command()

        self.assertTrue(os.path.exists(
            os.path.abspath(os.path.join(self.basedir, 'test-dir'))))
        self.assertUpdates([{'rc': 0}], self.builder.show())

    @defer.inlineCallbacks
    def test_already_exists(self):
        self.make_command(fs.MakeDirectory, dict(
            dir='workdir',
        ), True)

        yield self.run_command()

        self.assertUpdates([{'rc': 0}], self.builder.show())

    @defer.inlineCallbacks
    def test_existing_file(self):
        self.make_command(fs.MakeDirectory, dict(
            dir='test-file',
        ), True)
        open(os.path.join(self.basedir, 'test-file'), "w")

        yield self.run_command()

        self.assertIn({'rc': errno.EEXIST},
                      self.get_updates(),
                      self.builder.show())


class TestStatFile(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_non_existant(self):
        self.make_command(fs.StatFile, dict(
            file='no-such-file',
        ), True)

        yield self.run_command()

        self.assertIn({'rc': errno.ENOENT},
                      self.get_updates(),
                      self.builder.show())

    @defer.inlineCallbacks
    def test_directory(self):
        self.make_command(fs.StatFile, dict(
            file='workdir',
        ), True)

        yield self.run_command()

        import stat
        self.assertTrue(
            stat.S_ISDIR(self.get_updates()[0]['stat'][stat.ST_MODE]))
        self.assertIn({'rc': 0},
                      self.get_updates(),
                      self.builder.show())

    @defer.inlineCallbacks
    def test_file(self):
        self.make_command(fs.StatFile, dict(
            file='test-file',
        ), True)
        open(os.path.join(self.basedir, 'test-file'), "w")

        yield self.run_command()

        import stat
        self.assertTrue(
            stat.S_ISREG(self.get_updates()[0]['stat'][stat.ST_MODE]))
        self.assertIn({'rc': 0},
                      self.get_updates(),
                      self.builder.show())

    @defer.inlineCallbacks
    def test_file_workdir(self):
        self.make_command(fs.StatFile, dict(
            file='test-file',
            workdir='wd'
        ), True)
        os.mkdir(os.path.join(self.basedir, 'wd'))
        open(os.path.join(self.basedir, 'wd', 'test-file'), "w")

        yield self.run_command()

        import stat
        self.assertTrue(
            stat.S_ISREG(self.get_updates()[0]['stat'][stat.ST_MODE]))
        self.assertIn({'rc': 0},
                      self.get_updates(),
                      self.builder.show())


class TestGlobPath(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_non_existant(self):
        self.make_command(fs.GlobPath, dict(
            path='no-*-file',
        ), True)

        yield self.run_command()

        self.assertEqual(self.get_updates()[0]['files'], [])
        self.assertIn({'rc': 0},
                      self.get_updates(),
                      self.builder.show())

    @defer.inlineCallbacks
    def test_directory(self):
        self.make_command(fs.GlobPath, dict(
            path='[wxyz]or?d*',
        ), True)

        yield self.run_command()

        self.assertEqual(self.get_updates()[0]['files'],
                         [os.path.join(self.basedir, 'workdir')])
        self.assertIn({'rc': 0},
                      self.get_updates(),
                      self.builder.show())

    @defer.inlineCallbacks
    def test_file(self):
        self.make_command(fs.GlobPath, dict(
            path='t*-file',
        ), True)
        open(os.path.join(self.basedir, 'test-file'), "w")

        yield self.run_command()

        self.assertEqual(self.get_updates()[0]['files'],
                         [os.path.join(self.basedir, 'test-file')])
        self.assertIn({'rc': 0},
                      self.get_updates(),
                      self.builder.show())


class TestListDir(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_non_existant(self):
        self.make_command(fs.ListDir,
                          dict(dir='no-such-dir'),
                          True)
        yield self.run_command()

        self.assertIn({'rc': errno.ENOENT},
                      self.get_updates(),
                      self.builder.show())

    @defer.inlineCallbacks
    def test_dir(self):
        self.make_command(fs.ListDir, dict(
            dir='workdir',
        ), True)
        workdir = os.path.join(self.basedir, 'workdir')
        open(os.path.join(workdir, 'file1'), "w")
        open(os.path.join(workdir, 'file2'), "w")

        yield self.run_command()

        self.assertIn({'rc': 0},
                      self.get_updates(),
                      self.builder.show())

        self.failUnless(any([
            'files' in upd and sorted(upd['files']) == ['file1', 'file2']
            for upd in self.get_updates()]),
            self.builder.show())
