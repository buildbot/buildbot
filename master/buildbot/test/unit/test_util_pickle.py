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
import cStringIO

from twisted.trial import unittest

from buildbot.util import pickle


class TestClass(object):
    # referenced by the pickle, below
    pass


class Tests(unittest.TestCase):

    simplePickle = "(S'test'\np0\nccopy_reg\n_reconstructor\np1\n(cbuildbot.test.unit.test_util_pickle\nTestClass\np2\nc__builtin__\nobject\np3\nNtp4\nRp5\ntp6\n."
    sourcestampPickle = "(ibuildbot.sourcestamp\nSourceStamp\np0\n(dp2\nS'project'\np3\nS''\np4\nsS'repository'\np5\ng4\nsS'patch_info'\np6\nNsS'buildbot.sourcestamp.SourceStamp.persistenceVersion'\np7\nI3\nsS'patch'\np8\nNsS'codebase'\np9\ng4\nsS'_addSourceStampToDatabase_lock'\np10\nccopy_reg\n_reconstructor\np11\n(ctwisted.internet.defer\nDeferredLock\np12\nc__builtin__\nobject\np13\nNtp14\nRp15\n(dp16\nS'waiting'\np17\n(lp18\nsbsS'branch'\np19\nNsS'sourcestampsetid'\np20\nNsS'revision'\np21\nNsb."

    def assertSimplePickleContents(self, obj):
        self.assertIsInstance(obj, tuple)
        self.assertEqual(obj[0], 'test')
        self.assertIsInstance(obj[1], TestClass)

    def test_load(self):
        f = cStringIO.StringIO(self.simplePickle)
        obj = pickle.load(f)
        self.assertSimplePickleContents(obj)

    def test_loads(self):
        obj = pickle.loads(self.simplePickle)
        self.assertSimplePickleContents(obj)

    def test_sourcestamp(self):
        obj = pickle.loads(self.sourcestampPickle)
        self.assertIsInstance(obj, pickle.SourceStamp)
