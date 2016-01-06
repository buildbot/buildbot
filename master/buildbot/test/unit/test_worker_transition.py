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


from buildbot.worker_transition import _compat_name as compat_name


class CompatNameGeneration(unittest.TestCase):

    def test_generic_rename(self):
        self.assertEqual(compat_name("Worker"), "Slave")
        self.assertEqual(compat_name("worker"), "slave")
        self.assertEqual(compat_name("SomeWorkerStuff"), "SomeSlaveStuff")
        self.assertEqual(compat_name("theworkerstuff"), "theslavestuff")

        with self.assertRaises(AssertionError):
            compat_name("worKer")

    def test_patterned_rename(self):
        self.assertEqual(
            compat_name("SomeWorker", pattern="BuildWorker"),
            "SomeBuildSlave")
        self.assertEqual(
            compat_name("SomeWorker", pattern="Buildworker"),
            "SomeBuildslave")
        self.assertEqual(
            compat_name("someworker", pattern="buildworker"),
            "somebuildslave")

        with self.assertRaises(KeyError):
            compat_name("worker", pattern="missing")
