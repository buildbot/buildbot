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

import mock

from twisted.trial import unittest

from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning
from buildbot.worker_transition import WorkerAPICompatMixin
from buildbot.worker_transition import _deprecated_name as compat_name
from buildbot.worker_transition import define_old_worker_class
from buildbot.worker_transition import define_old_worker_class_alias
from buildbot.worker_transition import define_old_worker_func
from buildbot.worker_transition import define_old_worker_method
from buildbot.worker_transition import define_old_worker_property


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

        locals = {}
        define_old_worker_class_alias(
            locals, IWorker, pattern="BuildWorker")
        self.assertIn("IBuildSlave", locals)
        self.assertTrue(locals["IBuildSlave"] is IWorker)

        # TODO: Is there a way to detect usage of class alias and print
        # warning?

    def test_module_reload(self):
        # pylint: disable=function-redefined
        locals = {}

        class IWorker:
            pass

        define_old_worker_class_alias(
            locals, IWorker, pattern="BuildWorker")
        self.assertIn("IBuildSlave", locals)
        self.assertTrue(locals["IBuildSlave"] is IWorker)

        # "Reload" module
        class IWorker:
            pass

        define_old_worker_class_alias(
            locals, IWorker, pattern="BuildWorker")
        self.assertIn("IBuildSlave", locals)
        self.assertTrue(locals["IBuildSlave"] is IWorker)


class ClassWrapper(unittest.TestCase):

    def test_class_wrapper(self):
        class Worker(object):

            def __init__(self, arg, **kwargs):
                self.arg = arg
                self.kwargs = kwargs

        locals = {}
        define_old_worker_class(locals, Worker)
        self.assertIn("Slave", locals)
        Slave = locals["Slave"]
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

        locals = {}
        define_old_worker_class(locals, Worker, pattern="Buildworker")
        self.assertIn("Buildslave", locals)
        Buildslave = locals["Buildslave"]
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

        locals = {}
        define_old_worker_class(locals, Worker)
        self.assertIn("Slave", locals)
        Slave = locals["Slave"]
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

        locals = {}
        define_old_worker_class(locals, Worker)
        Slave = locals["Slave"]
        self.assertEqual(Slave.__doc__, Worker.__doc__)
        self.assertEqual(Slave.__module__, Worker.__module__)

    def test_module_reload(self):
        # pylint: disable=function-redefined
        locals = {}

        class Worker(object):

            def __init__(self, arg, **kwargs):
                self.arg = arg
                self.kwargs = kwargs

        define_old_worker_class(locals, Worker)
        self.assertIn("Slave", locals)
        self.assertTrue(issubclass(locals["Slave"], Worker))

        # "Reload" module
        class Worker(object):

            def __init__(self, arg, **kwargs):
                self.arg = arg
                self.kwargs = kwargs

        define_old_worker_class(locals, Worker)
        self.assertIn("Slave", locals)
        self.assertTrue(issubclass(locals["Slave"], Worker))


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

    def test_method_mocking(self):
        class C(object):

            def updateWorker(self, res):
                return res
            define_old_worker_method(locals(), updateWorker)

        c = C()

        c.updateWorker = mock.Mock(return_value="mocked")

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertEqual(c.updateWorker("test"), "mocked")

        with assertProducesWarning(DeprecatedWorkerNameWarning):
            self.assertEqual(c.updateSlave("test"), "mocked")


class FunctionWrapper(unittest.TestCase):

    def test_function_wrapper(self):
        def updateWorker(res):
            return res
        locals = {}
        define_old_worker_func(locals, updateWorker)

        self.assertIn("updateSlave", locals)

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertEqual(updateWorker("test"), "test")

        with assertProducesWarning(DeprecatedWorkerNameWarning):
            self.assertEqual(locals["updateSlave"]("test"), "test")

    def test_func_meta(self):
        def updateWorker(self, res):
            """docstring"""
            return res
        locals = {}
        define_old_worker_func(locals, updateWorker)

        self.assertEqual(locals["updateSlave"].__module__,
                         updateWorker.__module__)
        self.assertEqual(locals["updateSlave"].__doc__,
                         updateWorker.__doc__)

    def test_module_reload(self):
        # pylint: disable=function-redefined
        locals = {}

        def updateWorker(res):
            return res

        define_old_worker_func(locals, updateWorker)

        self.assertIn("updateSlave", locals)

        # "Reload" module
        def updateWorker(res):
            return res

        define_old_worker_func(locals, updateWorker)

        self.assertIn("updateSlave", locals)


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

    def test_attribute_setter(self):
        class C(WorkerAPICompatMixin):

            def __init__(self):
                self.workers = None
                self._registerOldWorkerAttr("workers", pattern="buildworker")

                self.workernames = None
                self._registerOldWorkerAttr("workernames")

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            c = C()

            c.workers = [1, 2, 3]
            c.workernames = ["a", "b", "c"]

        self.assertEqual(c.workers, [1, 2, 3])
        self.assertEqual(c.workernames, ["a", "b", "c"])

        with assertProducesWarning(DeprecatedWorkerNameWarning):
            c.buildslaves = [1, 2, 3]
        self.assertEqual(c.workers, [1, 2, 3])

        with assertProducesWarning(DeprecatedWorkerNameWarning):
            c.slavenames = ["a", "b", "c"]
        self.assertEqual(c.workernames, ["a", "b", "c"])

    def test_attribute_error(self):
        class C(WorkerAPICompatMixin):
            pass

        c = C()

        self.assertRaisesRegexp(
            AttributeError,
            "'C' object has no attribute 'abc'",
            lambda: c.abc)

    def test_static_attribute(self):
        class C(WorkerAPICompatMixin):
            value = 1

        c = C()

        self.assertEqual(c.value, 1)

    def test_properties(self):
        class C(WorkerAPICompatMixin):

            def __init__(self):
                self._value = 1

            @property
            def value(self):
                return self._value

            @value.setter
            def value(self, value):
                self._value = value

            @value.deleter
            def value(self):
                del self._value

        c = C()

        self.assertEqual(c._value, 1)
        self.assertEqual(c.value, 1)

        c.value = 2

        self.assertEqual(c._value, 2)
        self.assertEqual(c.value, 2)

        del c.value

        self.assertFalse(hasattr(c, "_value"))
        self.assertFalse(hasattr(c, "value"))
