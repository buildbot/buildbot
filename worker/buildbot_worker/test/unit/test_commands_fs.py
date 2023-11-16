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

from __future__ import absolute_import
from __future__ import print_function

import errno
import os
import shutil
import stat
import sys

from twisted.internet import defer
from twisted.python import runtime
from twisted.trial import unittest

from buildbot_worker.commands import fs
from buildbot_worker.commands import utils
from buildbot_worker.test.fake.runprocess import Expect
from buildbot_worker.test.util.command import CommandTestMixin
from buildbot_worker.test.util.compat import skipUnlessPlatformIs


class TestRemoveDirectory(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_simple_real(self):
        file_path = os.path.join(self.basedir, 'workdir')
        self.make_command(fs.RemoveDirectory, {'paths': [file_path]}, True)
        yield self.run_command()
        self.assertFalse(os.path.exists(os.path.abspath(file_path)))
        self.assertIn(('rc', 0), self.get_updates(), self.protocol_command.show())

    @skipUnlessPlatformIs('posix')
    @defer.inlineCallbacks
    def test_simple_posix(self):
        file_path = os.path.join(self.basedir, 'remove')
        self.make_command(fs.RemoveDirectory, {'paths': [file_path]}, True)

        self.patch_runprocess(
            Expect(["rm", "-rf", file_path], self.basedir, sendRC=0, timeout=120)
            .update('header', 'headers')
            .update('stdout', '')
            .update('rc', 0)
            .exit(0)
        )

        yield self.run_command()

        self.assertEqual(self.get_updates()[-2], ('rc', 0))
        self.assertIn('elapsed', self.get_updates()[-1])

    @defer.inlineCallbacks
    def test_simple_exception_real(self):
        if runtime.platformType == "posix":
            return  # we only use rmdirRecursive on windows

        def fail(dir):
            raise RuntimeError("oh noes")
        self.patch(utils, 'rmdirRecursive', fail)
        self.make_command(fs.RemoveDirectory, {'paths': ['workdir']}, True)
        yield self.run_command()

        self.assertIn(('rc', -1), self.get_updates(), self.protocol_command.show())

    @defer.inlineCallbacks
    def test_multiple_dirs_real(self):
        paths = [os.path.join(self.basedir, 'workdir'), os.path.join(self.basedir, 'sourcedir')]
        self.make_command(fs.RemoveDirectory, {'paths': paths}, True)
        yield self.run_command()

        for path in paths:
            self.assertFalse(os.path.exists(os.path.abspath(path)))
        self.assertIn(('rc', 0), self.get_updates(), self.protocol_command.show())

    @skipUnlessPlatformIs('posix')
    @defer.inlineCallbacks
    def test_multiple_dirs_posix(self):
        dir_1 = os.path.join(self.basedir, 'remove_1')
        dir_2 = os.path.join(self.basedir, 'remove_2')
        self.make_command(fs.RemoveDirectory, {'paths': [dir_1, dir_2]}, True)

        self.patch_runprocess(
            Expect(["rm", "-rf", dir_1], self.basedir, sendRC=0, timeout=120)
            .update('header', 'headers')
            .update('stdout', '')
            .update('rc', 0)
            .exit(0),
            Expect(["rm", "-rf", dir_2], self.basedir, sendRC=0, timeout=120)
            .update('header', 'headers')
            .update('stdout', '')
            .update('rc', 0)
            .exit(0)
        )

        yield self.run_command()

        self.assertEqual(self.get_updates()[-2], ('rc', 0))
        self.assertIn('elapsed', self.get_updates()[-1])

    @skipUnlessPlatformIs('posix')
    @defer.inlineCallbacks
    def test_rm_after_chmod(self):
        dir = os.path.join(self.basedir, 'remove')
        self.make_command(fs.RemoveDirectory, {'paths': [dir]}, True)

        self.patch_runprocess(
            Expect(["rm", "-rf", dir], self.basedir, sendRC=0, timeout=120)
            .update('header', 'headers')
            .update('stderr', 'permission denied')
            .update('rc', 1)
            .exit(1),
            Expect(['chmod', '-Rf', 'u+rwx', dir], self.basedir, sendRC=0, timeout=120)
            .update('header', 'headers')
            .update('stdout', '')
            .update('rc', 0)
            .exit(0),
            Expect(["rm", "-rf", dir], self.basedir, sendRC=0, timeout=120)
            .update('header', 'headers')
            .update('stdout', '')
            .update('rc', 0)
            .exit(0)
        )

        yield self.run_command()

        self.assertEqual(self.get_updates()[-2], ('rc', 0))
        self.assertIn('elapsed', self.get_updates()[-1])

    @skipUnlessPlatformIs('posix')
    @defer.inlineCallbacks
    def test_rm_after_failed(self):
        dir = os.path.join(self.basedir, 'remove')
        self.make_command(fs.RemoveDirectory, {'paths': [dir]}, True)

        self.patch_runprocess(
            Expect(["rm", "-rf", dir], self.basedir, sendRC=0, timeout=120)
            .update('header', 'headers')
            .update('stderr', 'permission denied')
            .update('rc', 1)
            .exit(1),
            Expect(['chmod', '-Rf', 'u+rwx', dir], self.basedir, sendRC=0, timeout=120)
            .update('header', 'headers')
            .update('stdout', '')
            .update('rc', 0)
            .exit(0),
            Expect(["rm", "-rf", dir], self.basedir, sendRC=0, timeout=120)
            .update('header', 'headers')
            .update('stdout', '')
            .update('rc', 1)
            .exit(1)
        )

        yield self.run_command()

        self.assertEqual(self.get_updates()[-2], ('rc', 1))
        self.assertIn('elapsed', self.get_updates()[-1])


class TestCopyDirectory(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_simple(self):
        from_path = os.path.join(self.basedir, 'workdir')
        to_path = os.path.join(self.basedir, 'copy')
        self.make_command(fs.CopyDirectory, {'from_path': from_path, 'to_path': to_path}, True)
        yield self.run_command()

        self.assertTrue(
            os.path.exists(os.path.abspath(to_path)))
        self.assertIn(('rc', 0),  # this may ignore a 'header' : '..', which is OK
                      self.get_updates(),
                      self.protocol_command.show())

    @defer.inlineCallbacks
    def test_simple_exception(self):
        if runtime.platformType == "posix":
            return  # we only use rmdirRecursive on windows

        def fail(src, dest):
            raise RuntimeError("oh noes")
        self.patch(shutil, 'copytree', fail)

        from_path = os.path.join(self.basedir, 'workdir')
        to_path = os.path.join(self.basedir, 'copy')
        self.make_command(fs.CopyDirectory, {'from_path': from_path, 'to_path': to_path}, True)
        yield self.run_command()

        self.assertIn(('rc', -1),
                      self.get_updates(),
                      self.protocol_command.show())


class TestMakeDirectory(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_empty_paths(self):
        self.make_command(fs.MakeDirectory, {'paths': []}, True)
        yield self.run_command()

        self.assertUpdates([('rc', 0)], self.protocol_command.show())

    @defer.inlineCallbacks
    def test_simple(self):
        paths = [os.path.join(self.basedir, 'test_dir')]
        self.make_command(fs.MakeDirectory, {'paths': paths}, True)
        yield self.run_command()

        self.assertTrue(os.path.exists(os.path.abspath(paths[0])))
        self.assertUpdates([('rc', 0)], self.protocol_command.show())

    @defer.inlineCallbacks
    def test_two_dirs(self):
        paths = [os.path.join(self.basedir, 'test-dir'), os.path.join(self.basedir, 'test-dir2')]
        self.make_command(fs.MakeDirectory, {'paths': paths}, True)
        yield self.run_command()

        for path in paths:
            self.assertTrue(os.path.exists(os.path.abspath(path)))

        self.assertUpdates([('rc', 0)], self.protocol_command.show())

    @defer.inlineCallbacks
    def test_already_exists(self):
        self.make_command(fs.MakeDirectory, {'paths': [os.path.join(self.basedir, 'workdir')]},
                          True)
        yield self.run_command()

        self.assertUpdates([('rc', 0)], self.protocol_command.show())

    @defer.inlineCallbacks
    def test_error_existing_file(self):
        paths = [os.path.join(self.basedir, 'test-file')]
        self.make_command(fs.MakeDirectory, {'paths': paths}, True)

        with open(paths[0], "w"):
            pass
        yield self.run_command()

        self.assertIn(('rc', errno.EEXIST), self.get_updates(), self.protocol_command.show())


class TestStatFile(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_non_existent(self):
        path = os.path.join(self.basedir, 'no-such-file')
        self.make_command(fs.StatFile, {'path': path}, True)
        yield self.run_command()

        self.assertIn(('rc', errno.ENOENT), self.get_updates(), self.protocol_command.show())

    @defer.inlineCallbacks
    def test_directory(self):
        path = os.path.join(self.basedir, 'workdir')

        self.make_command(fs.StatFile, {'path': path}, True)
        yield self.run_command()

        self.assertTrue(stat.S_ISDIR(self.get_updates()[0][1][stat.ST_MODE]))
        self.assertIn(('rc', 0), self.get_updates(), self.protocol_command.show())

    @defer.inlineCallbacks
    def test_file(self):
        path = os.path.join(self.basedir, 'test-file')

        self.make_command(fs.StatFile, {'path': path}, True)
        with open(os.path.join(self.basedir, 'test-file'), "w"):
            pass

        yield self.run_command()

        self.assertTrue(stat.S_ISREG(self.get_updates()[0][1][stat.ST_MODE]))
        self.assertIn(('rc', 0), self.get_updates(), self.protocol_command.show())

    @defer.inlineCallbacks
    def test_file_workdir(self):
        path = os.path.join(self.basedir, 'wd', 'test-file')
        self.make_command(fs.StatFile, {'path': path}, True)
        os.mkdir(os.path.join(self.basedir, 'wd'))
        with open(os.path.join(self.basedir, 'wd', 'test-file'), "w"):
            pass

        yield self.run_command()
        self.assertTrue(stat.S_ISREG(self.get_updates()[0][1][stat.ST_MODE]))
        self.assertIn(('rc', 0), self.get_updates(), self.protocol_command.show())


class TestGlobPath(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_non_existent(self):
        self.make_command(fs.GlobPath, {'path': os.path.join(self.basedir, 'no-*-file')}, True)
        yield self.run_command()

        self.assertEqual(self.get_updates()[0][1], [])
        self.assertIn(('rc', 0), self.get_updates(), self.protocol_command.show())

    @defer.inlineCallbacks
    def test_directory(self):
        self.make_command(fs.GlobPath, {'path': os.path.join(self.basedir, '[wxyz]or?d*')}, True)
        yield self.run_command()

        self.assertEqual(self.get_updates()[0][1], [os.path.join(self.basedir, 'workdir')])
        self.assertIn(('rc', 0), self.get_updates(), self.protocol_command.show())

    @defer.inlineCallbacks
    def test_file(self):
        self.make_command(fs.GlobPath, {'path': os.path.join(self.basedir, 't*-file')}, True)
        with open(os.path.join(self.basedir, 'test-file'), "w"):
            pass

        yield self.run_command()
        self.assertEqual(self.get_updates()[0][1], [os.path.join(self.basedir, 'test-file')])
        self.assertIn(('rc', 0), self.get_updates(), self.protocol_command.show())

    @defer.inlineCallbacks
    def test_recursive(self):
        self.make_command(fs.GlobPath, {'path': os.path.join(self.basedir, '**/*.txt')}, True)
        os.makedirs(os.path.join(self.basedir, 'test/testdir'))
        with open(os.path.join(self.basedir, 'test/testdir/test.txt'), 'w'):
            pass

        yield self.run_command()
        if sys.version_info[:] >= (3, 5):
            if sys.platform == 'win32':
                filename = 'test\\testdir\\test.txt'
            else:
                filename = 'test/testdir/test.txt'

            self.assertEqual(
                self.get_updates()[0][1], [os.path.join(self.basedir, filename)])
        else:
            self.assertEqual(self.get_updates()[0][1], [])
        self.assertIn(('rc', 0), self.get_updates(), self.protocol_command.show())


class TestListDir(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_non_existent(self):
        path = os.path.join(self.basedir, 'no-such-dir')

        self.make_command(fs.ListDir, {'path': path}, True)
        yield self.run_command()

        self.assertIn(('rc', errno.ENOENT), self.get_updates(), self.protocol_command.show())

    @defer.inlineCallbacks
    def test_dir(self):
        workdir = os.path.join(self.basedir, 'workdir')
        self.make_command(fs.ListDir, {'path': workdir}, True)
        with open(os.path.join(workdir, 'file1'), "w"):
            pass
        with open(os.path.join(workdir, 'file2'), "w"):
            pass

        yield self.run_command()

        def any(items):  # not a builtin on python-2.4
            for i in items:
                if i:
                    return True
            return None

        self.assertIn(('rc', 0), self.get_updates(), self.protocol_command.show())

        self.assertTrue(any('files' in upd and sorted(upd[1]) == ['file1', 'file2']
            for upd in self.get_updates()),
            self.protocol_command.show())


class TestRemoveFile(CommandTestMixin, unittest.TestCase):

    def setUp(self):
        self.setUpCommand()

    def tearDown(self):
        self.tearDownCommand()

    @defer.inlineCallbacks
    def test_simple(self):
        workdir = os.path.join(self.basedir, 'workdir')
        file1_path = os.path.join(workdir, 'file1')
        self.make_command(fs.RemoveFile, {'path': file1_path}, True)

        with open(file1_path, "w"):
            pass
        yield self.run_command()

        self.assertFalse(os.path.exists(file1_path))
        self.assertIn(('rc', 0),  # this may ignore a 'header' : '..', which is OK
                      self.get_updates(),
                      self.protocol_command.show())

    @defer.inlineCallbacks
    def test_simple_exception(self):
        workdir = os.path.join(self.basedir, 'workdir')
        file2_path = os.path.join(workdir, 'file2')

        self.make_command(fs.RemoveFile, {'path': file2_path}, True)
        yield self.run_command()

        self.assertIn(('rc', 2), self.get_updates(), self.protocol_command.show())
