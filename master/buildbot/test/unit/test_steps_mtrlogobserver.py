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

import mock

from twisted.enterprise import adbapi
from twisted.trial import unittest

from buildbot.steps import mtrlogobserver


class TestEqConnectionPool(unittest.TestCase):
    #
    # Test buildbot.steps.mtrlogobserver.EqConnectionPool class
    #

    def setUp(self):
        # patch adbapi.ConnectionPool constructor to do nothing
        self.patch(adbapi.ConnectionPool, "__init__", mock.Mock())

    def testEqSameInstance(self):
        # Test using '==' operator on same EqConnectionPool instance
        pool = mtrlogobserver.EqConnectionPool("MySQLdb",
                                               "host",
                                               "buildbot",
                                               "password",
                                               "db")
        self.assertTrue(pool == pool)

    def testEqSameArgs(self):
        # Test using '==' operator on two EqConnectionPool instances with
        # same arguments
        pool1 = mtrlogobserver.EqConnectionPool("MySQLdb",
                                                "host",
                                                "buildbot",
                                                "password",
                                                "db",
                                                extra="dummy")

        pool2 = mtrlogobserver.EqConnectionPool("MySQLdb",
                                                "host",
                                                "buildbot",
                                                "password",
                                                "db",
                                                extra="dummy")
        self.assertTrue(pool1 == pool2)

    def testEqDiffArgs(self):
        # Test using '==' operator on two EqConnectionPool instances with
        # different arguments
        pool1 = mtrlogobserver.EqConnectionPool("DummyDb1")
        pool2 = mtrlogobserver.EqConnectionPool("DummyDb2")
        self.assertFalse(pool1 == pool2)

    def testEqDiffType(self):
        # Test using '==' operator on an EqConnectionPool instance and object
        # of different type
        pool = mtrlogobserver.EqConnectionPool("DummyDb1")
        self.assertFalse(pool == object())

    def testNeSameInstance(self):
        # Test using '!=' operator on same EqConnectionPool instance
        pool = mtrlogobserver.EqConnectionPool("DummyDb1")
        self.assertFalse(pool != pool)

    def testNeSameArgs(self):
        # Test using '!=' operator on two EqConnectionPool instances with same
        # arguments
        pool1 = mtrlogobserver.EqConnectionPool("DummyDb1", "x", y="z")
        pool2 = mtrlogobserver.EqConnectionPool("DummyDb1", "x", y="z")
        self.assertFalse(pool1 != pool2)

    def testNeDiffArgs(self):
        # Test using '!=' operator on two EqConnectionPool instances with
        # different arguments
        pool1 = mtrlogobserver.EqConnectionPool("DummyDb1")
        pool2 = mtrlogobserver.EqConnectionPool("DummyDb2")
        self.assertTrue(pool1 != pool2)

    def testNeDiffType(self):
        # Test using '!=' operator on an EqConnectionPool instance and object
        # of different type
        pool = mtrlogobserver.EqConnectionPool("DummyDb1")
        self.assertTrue(pool != object())
