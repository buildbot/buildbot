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

from twisted.trial.unittest import TestCase

from buildbot.test.util.db import get_trial_parallel_from_cwd


class Tests(TestCase):
    def test_unknown(self):
        self.assertIsNone(get_trial_parallel_from_cwd(""))
        self.assertIsNone(get_trial_parallel_from_cwd("/"))
        self.assertIsNone(get_trial_parallel_from_cwd("/abc"))
        self.assertIsNone(get_trial_parallel_from_cwd("/abc/"))
        self.assertIsNone(get_trial_parallel_from_cwd("/abc/abc/1"))
        self.assertIsNone(get_trial_parallel_from_cwd("/abc/abc/1/"))
        self.assertIsNone(get_trial_parallel_from_cwd("/_trial_temp/abc/1"))
        self.assertIsNone(get_trial_parallel_from_cwd("/_trial_temp/abc/1/"))

    def test_single(self):
        self.assertIs(get_trial_parallel_from_cwd("_trial_temp"), False)
        self.assertIs(get_trial_parallel_from_cwd("_trial_temp/"), False)
        self.assertIs(get_trial_parallel_from_cwd("/_trial_temp"), False)
        self.assertIs(get_trial_parallel_from_cwd("/_trial_temp/"), False)
        self.assertIs(get_trial_parallel_from_cwd("/abc/_trial_temp"), False)
        self.assertIs(get_trial_parallel_from_cwd("/abc/_trial_temp/"), False)

    def test_index(self):
        self.assertEqual(get_trial_parallel_from_cwd("_trial_temp/0"), 0)
        self.assertEqual(get_trial_parallel_from_cwd("_trial_temp/0/"), 0)
        self.assertEqual(get_trial_parallel_from_cwd("_trial_temp/5"), 5)
        self.assertEqual(get_trial_parallel_from_cwd("_trial_temp/5/"), 5)
        self.assertEqual(get_trial_parallel_from_cwd("/_trial_temp/0"), 0)
        self.assertEqual(get_trial_parallel_from_cwd("/_trial_temp/0/"), 0)
        self.assertEqual(get_trial_parallel_from_cwd("/_trial_temp/5"), 5)
        self.assertEqual(get_trial_parallel_from_cwd("/_trial_temp/5/"), 5)
        self.assertEqual(get_trial_parallel_from_cwd("abc/_trial_temp/0"), 0)
        self.assertEqual(get_trial_parallel_from_cwd("abc/_trial_temp/0/"), 0)
        self.assertEqual(get_trial_parallel_from_cwd("abc/_trial_temp/5"), 5)
        self.assertEqual(get_trial_parallel_from_cwd("abc/_trial_temp/5/"), 5)
