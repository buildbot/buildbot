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

import re
import sys
import types

import mock

from twisted.python.deprecate import deprecatedModuleAttribute
from twisted.python.versions import Version
from twisted.trial import unittest

from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning
from buildbot.worker_transition import WorkerAPICompatMixin
from buildbot.worker_transition import _compat_name
from buildbot.worker_transition import deprecatedWorkerClassMethod
from buildbot.worker_transition import deprecatedWorkerClassProperty


class CompatNameGeneration(unittest.TestCase):

    def test_generic_rename(self):
        self.assertEqual(_compat_name("Worker"), "Slave")
        self.assertEqual(_compat_name("worker"), "slave")
        self.assertEqual(_compat_name("SomeWorkerStuff"), "SomeSlaveStuff")
        self.assertEqual(_compat_name("theworkerstuff"), "theslavestuff")

        with self.assertRaises(AssertionError):
            _compat_name("worKer")

    def test_dummy_rename(self):
        self.assertEqual(
            _compat_name("SomeWorker", compat_name="BuildSlave"),
            "BuildSlave")

        # Deprecated name by definition must contain "slave"
        with self.assertRaises(AssertionError):
            _compat_name("worker", compat_name="somestr")
        # New name always contains "worker" instead of "slave".
        with self.assertRaises(AssertionError):
            _compat_name("somestr", compat_name="slave")


class test_deprecatedWorkerClassProperty(unittest.TestCase):

    def test_produces_warning(self):
        class C(object):

            @property
            def workername(self):
                return "name"
            deprecatedWorkerClassProperty(locals(), workername)

        c = C()

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertEqual(c.workername, "name")

        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern="'slavename' property is deprecated, "
                                "use 'workername' instead"):
            self.assertEqual(c.slavename, "name")


class test_deprecatedWorkerClassMethod(unittest.TestCase):

    def test_method_wrapper(self):
        class C(object):

            def updateWorker(self, res):
                return res
            deprecatedWorkerClassMethod(locals(), updateWorker)

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
            deprecatedWorkerClassMethod(locals(), updateWorker)

        self.assertEqual(C.updateSlave.__module__, C.updateWorker.__module__)
        self.assertEqual(C.updateSlave.__doc__, C.updateWorker.__doc__)

    def test_method_mocking(self):
        class C(object):

            def updateWorker(self, res):
                return res
            deprecatedWorkerClassMethod(locals(), updateWorker)

        c = C()

        c.updateWorker = mock.Mock(return_value="mocked")

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertEqual(c.updateWorker("test"), "mocked")

        with assertProducesWarning(DeprecatedWorkerNameWarning):
            self.assertEqual(c.updateSlave("test"), "mocked")


class AttributeMixin(unittest.TestCase):

    def test_attribute(self):
        class C(WorkerAPICompatMixin):

            def __init__(self):
                self.workers = [1, 2, 3]
                self._registerOldWorkerAttr("workers", name="buildslaves")

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
                self._registerOldWorkerAttr("workers", name="buildslaves")

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

        with self.assertRaisesRegex(AttributeError,
                                    "'C' object has no attribute 'abc'"):
            c.abc()

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
