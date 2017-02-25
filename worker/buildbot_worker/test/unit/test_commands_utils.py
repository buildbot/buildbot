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
from __future__ import division
from __future__ import print_function

import os
import shutil
import sys

import twisted.python.procutils
from twisted.python import runtime
from twisted.trial import unittest

from buildbot_worker.commands import utils


class GetCommand(unittest.TestCase):

    def setUp(self):
        # monkey-patch 'which' to return something appropriate
        self.which_results = {}

        def which(arg):
            return self.which_results.get(arg, [])
        self.patch(twisted.python.procutils, 'which', which)
        # note that utils.py currently imports which by name, so we
        # patch it there, too
        self.patch(utils, 'which', which)

    def set_which_results(self, results):
        self.which_results = results

    def test_getCommand_empty(self):
        self.set_which_results({
            'xeyes': [],
        })
        self.assertRaises(RuntimeError, lambda: utils.getCommand('xeyes'))

    def test_getCommand_single(self):
        self.set_which_results({
            'xeyes': ['/usr/bin/xeyes'],
        })
        self.assertEqual(utils.getCommand('xeyes'), '/usr/bin/xeyes')

    def test_getCommand_multi(self):
        self.set_which_results({
            'xeyes': ['/usr/bin/xeyes', '/usr/X11/bin/xeyes'],
        })
        self.assertEqual(utils.getCommand('xeyes'), '/usr/bin/xeyes')

    def test_getCommand_single_exe(self):
        self.set_which_results({
            'xeyes': ['/usr/bin/xeyes'],
            # it should not select this option, since only one matched
            # to begin with
            'xeyes.exe': [r'c:\program files\xeyes.exe'],
        })
        self.assertEqual(utils.getCommand('xeyes'), '/usr/bin/xeyes')

    def test_getCommand_multi_exe(self):
        self.set_which_results({
            'xeyes': [r'c:\program files\xeyes.com', r'c:\program files\xeyes.exe'],
            'xeyes.exe': [r'c:\program files\xeyes.exe'],
        })
        # this one will work out differently depending on platform..
        if runtime.platformType == 'win32':
            self.assertEqual(
                utils.getCommand('xeyes'), r'c:\program files\xeyes.exe')
        else:
            self.assertEqual(
                utils.getCommand('xeyes'), r'c:\program files\xeyes.com')


class RmdirRecursive(unittest.TestCase):

    # this is more complicated than you'd think because Twisted doesn't
    # rmdir its test directory very well, either..

    def setUp(self):
        self.target = 'testdir'
        try:
            if os.path.exists(self.target):
                shutil.rmtree(self.target)
        except Exception:
            # this test will probably fail anyway
            e = sys.exc_info()[0]
            raise unittest.SkipTest("could not clean before test: %s" % (e,))

        # fill it with some files
        os.mkdir(os.path.join(self.target))
        with open(os.path.join(self.target, "a"), "w"):
            pass
        os.mkdir(os.path.join(self.target, "d"))
        with open(os.path.join(self.target, "d", "a"), "w"):
            pass
        os.mkdir(os.path.join(self.target, "d", "d"))
        with open(os.path.join(self.target, "d", "d", "a"), "w"):
            pass

    def tearDown(self):
        try:
            if os.path.exists(self.target):
                shutil.rmtree(self.target)
        except Exception:
            print(
                "\n(target directory was not removed by test, and cleanup failed too)\n")
            raise

    def test_rmdirRecursive_easy(self):
        utils.rmdirRecursive(self.target)
        self.assertFalse(os.path.exists(self.target))

    def test_rmdirRecursive_symlink(self):
        # this was intended as a regression test for #792, but doesn't seem
        # to trigger it.  It can't hurt to check it, all the same.
        if runtime.platformType == 'win32':
            raise unittest.SkipTest("no symlinks on this platform")
        os.mkdir("noperms")
        with open("noperms/x", "w"):
            pass
        os.chmod("noperms/x", 0)
        try:
            os.symlink("../noperms", os.path.join(self.target, "link"))
            utils.rmdirRecursive(self.target)
            # that shouldn't delete the target of the symlink
            self.assertTrue(os.path.exists("noperms"))
        finally:
            # even Twisted can't clean this up very well, so try hard to
            # clean it up ourselves..
            os.chmod("noperms/x", 0o777)
            os.unlink("noperms/x")
            os.rmdir("noperms")

        self.assertFalse(os.path.exists(self.target))
