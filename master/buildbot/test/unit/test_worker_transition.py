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

import warnings
import contextlib

from twisted.trial import unittest


from buildbot.worker_transition import (
    _compat_name as compat_name, define_old_worker_class_alias,
    define_old_worker_class, DeprecatedWorkerNameError,
)


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


class ClassAlias(unittest.TestCase):

    def test_class_alias(self):
        class IWorker:
            pass

        globals = {}
        define_old_worker_class_alias(
            globals, IWorker, pattern="BuildWorker")
        self.assertIn("IBuildSlave", globals)
        self.assertIs(globals["IBuildSlave"], IWorker)

        # TODO: Is there a way to detect usage of class alias and print
        # warning?


class ClassWrapper(unittest.TestCase):

    @contextlib.contextmanager
    def _assertProducesWarning(self):
        with warnings.catch_warnings(record=True) as w:
            # Cause all warnings to always be triggered.
            warnings.simplefilter("always")

            yield

            # Verify some things
            self.assertEqual(len(w), 1)
            self.assertTrue(issubclass(w[-1].category,
                                       DeprecatedWorkerNameError))
            self.assertIn("deprecated", str(w[-1].message))

    def test_class_wrapper(self):
        class Worker(object):
            def __init__(self, arg, **kwargs):
                self.arg = arg
                self.kwargs = kwargs

        globals = {}
        define_old_worker_class(globals, Worker)
        self.assertIn("Slave", globals)
        Slave = globals["Slave"]
        self.assertTrue(issubclass(Slave, Worker))

        with self._assertProducesWarning():
            # Trigger a warning.
            slave = Slave("arg", a=1, b=2)

        self.assertEqual(slave.arg, "arg")
        self.assertEqual(slave.kwargs, dict(a=1, b=2))

    def test_class_with_new_wrapper(self):
        class Worker(object):
            def __init__(self, arg, **kwargs):
                self.arg = arg
                self.kwargs = kwargs

            def __new__(cls, *args, **kwargs):
                instance = object.__new__(cls)
                instance.new_args = args
                instance.new_kwargs = kwargs
                return instance

        globals = {}
        define_old_worker_class(globals, Worker)
        self.assertIn("Slave", globals)
        Slave = globals["Slave"]
        self.assertTrue(issubclass(Slave, Worker))

        with self._assertProducesWarning():
            # Trigger a warning.
            slave = Slave("arg", a=1, b=2)

        self.assertEqual(slave.arg, "arg")
        self.assertEqual(slave.kwargs, dict(a=1, b=2))
        self.assertEqual(slave.new_args, ("arg",))
        self.assertEqual(slave.new_kwargs, dict(a=1, b=2))
