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
from twisted.trial import unittest
from mock import Mock

from buildslave.test.util.command import CommandTestMixin
from buildslave.commands import fs
from twisted.python import runtime
from twisted.internet import defer
from buildslave.commands import utils

class TestRemoveDirectory(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.make_command(fs.RemoveDirectory, dict(
            dir='workdir',
        ), True)
        d = self.run_command()

        def check(_):
            self.assertFalse(os.path.exists(os.path.abspath(os.path.join(self.basedir,'workdir'))))
            self.assertIn({'rc': 0},
                    self.get_updates(),
                    self.builder.show())
        d.addCallback(check)
        return d

    def test_simple_exception(self):
        if runtime.platformType == "posix":
            return # we only use rmdirRecursive on windows
        def fail(dir):
            raise RuntimeError("oh noes")
        self.patch(utils, 'rmdirRecursive', fail)
        self.make_command(fs.RemoveDirectory, dict(
            dir='workdir',
        ), True)
        d = self.run_command()

        def check(_):
            self.assertIn({'rc': -1}, self.get_updates(),
                    self.builder.show())
        d.addCallback(check)
        return d

    def test_multiple_dirs(self):
        self.make_command(fs.RemoveDirectory, dict(
            dir=['workdir', 'sourcedir'],
        ), True)
        d = self.run_command()

        def check(_):
            for dirname in ['workdir', 'sourcedir']:
                self.assertFalse(os.path.exists(os.path.abspath(os.path.join(self.basedir, dirname))))
            self.assertIn({'rc': 0},
                            self.get_updates(),
                            self.builder.show())
        d.addCallback(check)
        return d

class TestCopyDirectory(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.make_command(fs.CopyDirectory, dict(
            fromdir='workdir',
            todir='copy',
        ), True)
        d = self.run_command()

        def check(_):
            self.assertTrue(os.path.exists(os.path.abspath(os.path.join(self.basedir,'copy'))))
            self.assertIn({'rc': 0}, # this may ignore a 'header' : '..', which is OK
                    self.get_updates(),
                    self.builder.show())
        d.addCallback(check)
        return d

    def test_simple_exception(self):
        if runtime.platformType == "posix":
            return # we only use rmdirRecursive on windows
        def fail(src, dest):
            raise RuntimeError("oh noes")
        self.patch(shutil, 'copytree', fail)
        self.make_command(fs.CopyDirectory, dict(
            fromdir='workdir',
            todir='copy',
        ), True)
        d = self.run_command()

        def check(_):
            self.assertIn({'rc': -1},
                    self.get_updates(),
                    self.builder.show())
        d.addCallback(check)
        return d

class TestMakeDirectory(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_simple(self):
        self.make_command(fs.MakeDirectory, dict(
            dir='test-dir',
        ), True)
        d = self.run_command()

        def check(_):
            self.assertTrue(os.path.exists(os.path.abspath(os.path.join(self.basedir,'test-dir'))))
            self.assertUpdates(
                    [{'rc': 0}],
                    self.builder.show())
        d.addCallback(check)
        return d

    def test_already_exists(self):
        self.make_command(fs.MakeDirectory, dict(
            dir='workdir',
        ), True)
        d = self.run_command()

        def check(_):
            self.assertUpdates(
                    [{'rc': 0}],
                    self.builder.show())
        d.addCallback(check)
        return d

    def test_existing_file(self):
        self.make_command(fs.MakeDirectory, dict(
            dir='test-file',
        ), True)
        open(os.path.join(self.basedir, 'test-file'), "w")
        d = self.run_command()

        def check(_):
            self.assertUpdates([{'rc': 1}], self.builder.show())
        d.addErrback(check)
        return d

class TestStatFile(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    def test_non_existant(self):
        self.make_command(fs.StatFile, dict(
            file='no-such-file',
        ), True)
        d = self.run_command()

        def check(_):
            self.assertUpdates(
                    [{'rc': 1}],
                    self.builder.show())
        d.addCallback(check)
        return d

    def test_directory(self):
        self.make_command(fs.StatFile, dict(
            file='workdir',
        ), True)
        d = self.run_command()

        def check(_):
            import stat
            self.assertTrue(stat.S_ISDIR(self.get_updates()[0]['stat'][stat.ST_MODE]))
            self.assertIn({'rc': 0},
                    self.get_updates(),
                    self.builder.show())
        d.addCallback(check)
        return d

    def test_file(self):
        self.make_command(fs.StatFile, dict(
            file='test-file',
        ), True)
        open(os.path.join(self.basedir, 'test-file'), "w")

        d = self.run_command()

        def check(_):
            import stat
            self.assertTrue(stat.S_ISREG(self.get_updates()[0]['stat'][stat.ST_MODE]))
            self.assertIn({'rc': 0},
                    self.get_updates(),
                    self.builder.show())
        d.addCallback(check)
        return d


class TestListTreeFunc(unittest.TestCase):
    """
    test fs._list_tree() function
    """
    ROOTDIR = "rootdir"

    OS_WALK_RES = [
        (ROOTDIR,
         ["subdir1"],
         ["rootfile1", "rootfile2"]),
        (os.path.join("rootdir", "subdir1"),
         [],
         ["subdirfile1.pkg", "subdirfile2.dat"])]

    RES_ALL = [
        ("",
         ["subdir1"],
         ["rootfile1", "rootfile2"]),
        ("subdir1",
         [],
         ["subdirfile1.pkg", "subdirfile2.dat"])]

    RES_FILTERED = [
        ("",
         ["subdir1"],
         []),
        ("subdir1",
         [],
         ["subdirfile1.pkg"])]

    def setUp(self):
        self.patch(os, "walk", Mock(return_value=self.OS_WALK_RES))

    def test_all(self):
        # test with an 'all inclusive' filter
        self.assertEquals(fs._list_tree(self.ROOTDIR, ""),
                          self.RES_ALL)

    def test_filter(self):
        # list only .pkg files
        self.assertEquals(fs._list_tree(self.ROOTDIR, ".*pkg$"),
                          self.RES_FILTERED)


class TestListTree(CommandTestMixin, unittest.TestCase):
    WORKDIR = "wkrdir"
    DIR = "tstdir"
    FILE_FILTER = "file_fltr"

    def setUp(self):
        self.setUpCommand()

        self._list_tree = Mock()
        self.patch(fs, "_list_tree", self._list_tree)

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_lstree(self):
        self.make_command(fs.ListTree,
                          dict(workdir=self.WORKDIR,
                               dir=self.DIR,
                               file_filter=self.FILE_FILTER))

        yield self.run_command()

        # check that fs._list_tree() was called with correct arguments
        self._list_tree.assert_called_once_with(
            os.path.join(self.basedir, self.WORKDIR, self.DIR),
            self.FILE_FILTER)

        # check that command 'returned' correct results
        updates = self.get_updates()
        self.assertIn({"rc": 0}, updates)
        self.assertIn({"nodes": self._list_tree.return_value}, updates)
