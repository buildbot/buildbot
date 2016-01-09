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

from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning
from buildbot.worker_transition import WorkerAPICompatMixin
from buildbot.worker_transition import define_old_worker_class
from buildbot.worker_transition import define_old_worker_class_alias
from buildbot.worker_transition import define_old_worker_func
from buildbot.worker_transition import define_old_worker_method
from buildbot.worker_transition import define_old_worker_property
from buildbot.worker_transition import deprecated_name as compat_name


class CompatNameGeneration(unittest.TestCase):

    def test_generic_rename(self):
        self.assertEqual(compat_name("Worker"), "Slave")
        self.assertEqual(compat_name("worker"), "slave")
        self.assertEqual(compat_name("SomeWorkerStuff"), "SomeSlaveStuff")
        self.assertEqual(compat_name("theworkerstuff"), "theslavestuff")

        self.assertRaises(AssertionError, compat_name, "worKer")

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

        self.assertRaises(KeyError, compat_name, "worker", pattern="missing")


class ClassAlias(unittest.TestCase):

    def test_class_alias(self):
        class IWorker:
            pass

        globals = {}
        define_old_worker_class_alias(
            globals, IWorker, pattern="BuildWorker")
        self.assertIn("IBuildSlave", globals)
        self.assertTrue(globals["IBuildSlave"] is IWorker)

        # TODO: Is there a way to detect usage of class alias and print
        # warning?


class ClassWrapper(unittest.TestCase):

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

        with assertProducesWarning(DeprecatedWorkerNameWarning):
            # Trigger a warning.
            slave = Slave("arg", a=1, b=2)

        self.assertEqual(slave.arg, "arg")
        self.assertEqual(slave.kwargs, dict(a=1, b=2))

    def test_class_wrapper_pattern(self):
        class Worker(object):

            def __init__(self, arg, **kwargs):
                self.arg = arg
                self.kwargs = kwargs

        globals = {}
        define_old_worker_class(globals, Worker, pattern="Buildworker")
        self.assertIn("Buildslave", globals)
        Buildslave = globals["Buildslave"]
        self.assertTrue(issubclass(Buildslave, Worker))

        with assertProducesWarning(DeprecatedWorkerNameWarning):
            # Trigger a warning.
            slave = Buildslave("arg", a=1, b=2)

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

        with assertProducesWarning(DeprecatedWorkerNameWarning):
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


class PropertyWrapper(unittest.TestCase):

    def test_property_wrapper(self):
        class C(object):

            @property
            def workername(self):
                return "name"
            define_old_worker_property(locals(), "workername")

        c = C()

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertEqual(c.workername, "name")

        with assertProducesWarning(DeprecatedWorkerNameWarning):
            self.assertEqual(c.slavename, "name")


class MethodWrapper(unittest.TestCase):

    def test_method_wrapper(self):
        class C(object):

            def updateWorker(self, res):
                return res
            define_old_worker_method(locals(), updateWorker)

        c = C()

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertEqual(c.updateWorker("test"), "test")

        with assertProducesWarning(DeprecatedWorkerNameWarning):
            self.assertEqual(c.updateSlave("test"), "test")

    def test_method_meta(self):
        class C(object):

            def updateWorker(self, res):
                """docstring"""
                return res
            define_old_worker_method(locals(), updateWorker)

        self.assertEqual(C.updateSlave.__module__, C.updateWorker.__module__)
        self.assertEqual(C.updateSlave.__doc__, C.updateWorker.__doc__)


class FunctionWrapper(unittest.TestCase):

    def test_function_wrapper(self):
        def updateWorker(res):
            return res
        globals = {}
        define_old_worker_func(globals, updateWorker)

        self.assertIn("updateSlave", globals)

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertEqual(updateWorker("test"), "test")

        with assertProducesWarning(DeprecatedWorkerNameWarning):
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


class AttributeMixin(unittest.TestCase):

    def test_attribute(self):
        class C(WorkerAPICompatMixin):

            def __init__(self):
                self.workers = [1, 2, 3]
                self._registerOldWorkerAttr("workers", pattern="buildworker")

                self.workernames = ["a", "b", "c"]
                self._registerOldWorkerAttr("workernames")

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            c = C()

            self.assertEqual(c.workers, [1, 2, 3])
            self.assertEqual(c.workernames, ["a", "b", "c"])

        with assertProducesWarning(DeprecatedWorkerNameWarning):
            self.assertEqual(c.buildslaves, [1, 2, 3])

        with assertProducesWarning(DeprecatedWorkerNameWarning):
            self.assertEqual(c.slavenames, ["a", "b", "c"])
