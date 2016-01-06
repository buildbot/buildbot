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
    define_old_worker_class, define_old_worker_property,
    define_old_worker_method, define_old_worker_func,
    DeprecatedWorkerNameError, WorkerAPICompatMixin,
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


class _TestBase(unittest.TestCase):

    @contextlib.contextmanager
    def _assertProducesWarning(self, num_warnings=1):
        with warnings.catch_warnings(record=True) as w:
            # Cause all warnings to always be triggered.
            warnings.simplefilter("always")

            yield

            # Verify some things
            self.assertEqual(len(w), num_warnings)
            for warning in w:
                self.assertTrue(issubclass(warning.category,
                                           DeprecatedWorkerNameError))
                self.assertIn("deprecated", str(warning.message))

    @contextlib.contextmanager
    def _assertNotProducesWarning(self):
        with warnings.catch_warnings(record=True) as w:
            # Cause all warnings to always be triggered.
            warnings.simplefilter("always")

            yield

            # Verify some things
            self.assertEqual(len(w), 0)


class ClassWrapper(_TestBase):

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

    def test_class_meta(self):
        class Worker(object):
            """docstring"""

        globals = {}
        define_old_worker_class(globals, Worker)
        Slave = globals["Slave"]
        self.assertEqual(Slave.__doc__, Worker.__doc__)
        self.assertEqual(Slave.__module__, Worker.__module__)


class PropertyWrapper(_TestBase):

    def test_property_wrapper(self):
        class C(object):
            @property
            def workername(self):
                return "name"
            define_old_worker_property(locals(), "workername")

        c = C()

        with self._assertNotProducesWarning():
            self.assertEqual(c.workername, "name")

        with self._assertProducesWarning():
            self.assertEqual(c.slavename, "name")


class MethodWrapper(_TestBase):

    def test_method_wrapper(self):
        class C(object):
            def updateWorker(self, res):
                return res
            define_old_worker_method(locals(), updateWorker)

        c = C()

        with self._assertNotProducesWarning():
            self.assertEqual(c.updateWorker("test"), "test")

        with self._assertProducesWarning():
            self.assertEqual(c.updateSlave("test"), "test")

    def test_method_meta(self):
        class C(object):
            def updateWorker(self, res):
                """docstring"""
                return res
            define_old_worker_method(locals(), updateWorker)

        self.assertEqual(C.updateSlave.__module__, C.updateWorker.__module__)
        self.assertEqual(C.updateSlave.__doc__, C.updateWorker.__doc__)


class FunctionWrapper(_TestBase):

    def test_function_wrapper(self):
        def updateWorker(res):
            return res
        globals = {}
        define_old_worker_func(globals, updateWorker)

        self.assertIn("updateSlave", globals)

        with self._assertNotProducesWarning():
            self.assertEqual(updateWorker("test"), "test")

        with self._assertProducesWarning():
            self.assertEqual(globals["updateSlave"]("test"), "test")

    def test_func_meta(self):
        def updateWorker(self, res):
            """docstring"""
            return res
        globals = {}
        define_old_worker_func(globals, updateWorker)

        self.assertEqual(globals["updateSlave"].__module__,
                         updateWorker.__module__)
        self.assertEqual(globals["updateSlave"].__doc__,
                         updateWorker.__doc__)


class AttributeMixin(_TestBase):

    def test_attribute(self):
        class C(WorkerAPICompatMixin):
            def __init__(self):
                self.workers = [1, 2, 3]
                self._registerOldWorkerAttr("workers", pattern="buildworker")

        with self._assertNotProducesWarning():
            c = C()

            self.assertEqual(c.workers, [1, 2, 3])

        with self._assertProducesWarning():
            self.assertEqual(c.buildslaves, [1, 2, 3])
