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
"""
Unit tests for the plugin framework
"""

from __future__ import absolute_import
from __future__ import print_function

import re

import mock

from twisted.trial import unittest
from zope.interface import implementer

import buildbot.plugins.db
from buildbot.errors import PluginDBError
from buildbot.interfaces import IPlugin
from buildbot.test.util.warnings import assertNotProducesWarnings
from buildbot.test.util.warnings import assertProducesWarning
from buildbot.worker_transition import DeprecatedWorkerAPIWarning
from buildbot.worker_transition import DeprecatedWorkerNameWarning

# buildbot.plugins.db needs to be imported for patching, however just 'db' is
# much shorter for using in tests
db = buildbot.plugins.db


class FakeEntry(object):

    """
    An entry suitable for unit tests
    """

    def __init__(self, name, project_name, version, fail_require, value):
        self._name = name
        self._dist = mock.Mock(spec_set=['project_name', 'version'])
        self._dist.project_name = project_name
        self._dist.version = version
        self._fail_require = fail_require
        self._value = value

    @property
    def name(self):
        "entry name"
        return self._name

    @property
    def dist(self):
        "dist thingie"
        return self._dist

    def require(self):
        """
        handle external dependencies
        """
        if self._fail_require:
            raise RuntimeError('Fail require as requested')

    def load(self):
        """
        handle loading
        """
        return self._value


class ITestInterface(IPlugin):

    """
    test interface
    """
    def hello(name):
        "Greets by :param:`name`"


@implementer(ITestInterface)
class ClassWithInterface(object):

    """
    a class to implement a simple interface
    """

    def __init__(self, name=None):
        self._name = name

    def hello(self, name=None):
        'implement the required method'
        return name or self._name


class ClassWithNoInterface(object):

    """
    just a class
    """


# NOTE: buildbot.plugins.db prepends the group with common namespace --
# 'buildbot.'
_FAKE_ENTRIES = {
    'buildbot.interface': [
        FakeEntry('good', 'non-existent', 'irrelevant', False,
                  ClassWithInterface),
        FakeEntry('deep.path', 'non-existent', 'irrelevant', False,
                  ClassWithInterface)
    ],
    'buildbot.interface_failed': [
        FakeEntry('good', 'non-existent', 'irrelevant', True,
                  ClassWithInterface)
    ],
    'buildbot.no_interface': [
        FakeEntry('good', 'non-existent', 'irrelevant', False,
                  ClassWithNoInterface)
    ],
    'buildbot.no_interface_again': [
        FakeEntry('good', 'non-existent', 'irrelevant', False,
                  ClassWithNoInterface)
    ],
    'buildbot.no_interface_failed': [
        FakeEntry('good', 'non-existent', 'irrelevant', True,
                  ClassWithNoInterface)
    ],
    'buildbot.duplicates': [
        FakeEntry('good', 'non-existent', 'first', False,
                  ClassWithNoInterface),
        FakeEntry('good', 'non-existent', 'second', False,
                  ClassWithNoInterface)
    ]
}


def provide_fake_entries(group):
    """
    give a set of fake entries for known groups
    """
    return _FAKE_ENTRIES.get(group, [])


@mock.patch('buildbot.plugins.db.iter_entry_points', provide_fake_entries)
class TestBuildbotPlugins(unittest.TestCase):

    def setUp(self):
        buildbot.plugins.db._DB = buildbot.plugins.db._PluginDB()

    def test_check_group_registration(self):
        with mock.patch.object(buildbot.plugins.db, '_DB', db._PluginDB()):
            # The groups will be prepended with namespace, so info() will
            # return a dictionary with right keys, but no data
            groups = set(_FAKE_ENTRIES.keys())
            for group in groups:
                db.get_plugins(group)

            registered = set(db.info().keys())
            self.assertEqual(registered, groups)
            self.assertEqual(registered, set(db.namespaces()))

    def test_interface_provided_simple(self):
        # Basic check before the actual test
        self.assertTrue(ITestInterface.implementedBy(ClassWithInterface))

        plugins = db.get_plugins('interface', interface=ITestInterface)

        self.assertTrue('good' in plugins.names)

        result_get = plugins.get('good')
        result_getattr = plugins.good
        self.assertFalse(result_get is None)
        self.assertTrue(result_get is result_getattr)

        # Make sure we actually got our class
        greeter = result_get('yes')
        self.assertEqual('yes', greeter.hello())
        self.assertEqual('no', greeter.hello('no'))

    def test_missing_plugin(self):
        plugins = db.get_plugins('interface', interface=ITestInterface)

        self.assertRaises(AttributeError, getattr, plugins, 'bad')
        self.assertRaises(PluginDBError, plugins.get, 'bad')
        self.assertRaises(PluginDBError, plugins.get, 'good.extra')

    def test_interface_provided_deep(self):
        # Basic check before the actual test
        self.assertTrue(ITestInterface.implementedBy(ClassWithInterface))

        plugins = db.get_plugins('interface', interface=ITestInterface)

        self.assertTrue('deep.path' in plugins.names)

        self.assertTrue('deep.path' in plugins)
        self.assertFalse('even.deeper.path' in plugins)

        result_get = plugins.get('deep.path')
        result_getattr = plugins.deep.path
        self.assertFalse(result_get is None)
        self.assertTrue(result_get is result_getattr)

        # Make sure we actually got our class
        greeter = result_get('yes')
        self.assertEqual('yes', greeter.hello())
        self.assertEqual('no', greeter.hello('no'))

    def test_interface_provided_deps_failed(self):
        plugins = db.get_plugins('interface_failed', interface=ITestInterface,
                                 check_extras=True)
        self.assertRaises(PluginDBError, plugins.get, 'good')

    def test_required_interface_not_provided(self):
        plugins = db.get_plugins('no_interface_again',
                                 interface=ITestInterface)
        self.assertTrue(plugins._interface is ITestInterface)
        self.assertRaises(PluginDBError, plugins.get, 'good')

    def test_no_interface_provided(self):
        plugins = db.get_plugins('no_interface')
        self.assertFalse(plugins.get('good') is None)

    def test_no_interface_provided_deps_failed(self):
        plugins = db.get_plugins('no_interface_failed', check_extras=True)
        self.assertRaises(PluginDBError, plugins.get, 'good')

    def test_failure_on_dups(self):
        self.assertRaises(PluginDBError, db.get_plugins, 'duplicates',
                          load_now=True)

    def test_get_info_on_a_known_plugin(self):
        plugins = db.get_plugins('interface')
        self.assertEqual(('non-existent', 'irrelevant'), plugins.info('good'))

    def test_failure_on_unknown_plugin_info(self):
        plugins = db.get_plugins('interface')
        self.assertRaises(PluginDBError, plugins.info, 'bad')

    def test_failure_on_unknown_plugin_get(self):
        plugins = db.get_plugins('interface')
        self.assertRaises(PluginDBError, plugins.get, 'bad')


class SimpleFakeEntry(FakeEntry):

    def __init__(self, name, value):
        FakeEntry.__init__(self, name, 'non-existent', 'irrelevant', False,
                           value)


_WORKER_FAKE_ENTRIES = {
    'buildbot.worker': [
        SimpleFakeEntry('Worker', ClassWithInterface),
        SimpleFakeEntry('EC2LatentWorker', ClassWithInterface),
        SimpleFakeEntry('LibVirtWorker', ClassWithInterface),
        SimpleFakeEntry('OpenStackLatentWorker', ClassWithInterface),
        SimpleFakeEntry('newthirdparty', ClassWithInterface),
        SimpleFakeEntry('deep.newthirdparty', ClassWithInterface),
    ],
    'buildbot.buildslave': [
        SimpleFakeEntry('thirdparty', ClassWithInterface),
        SimpleFakeEntry('deep.thirdparty', ClassWithInterface),
    ],
    'buildbot.util': [
        SimpleFakeEntry('WorkerLock', ClassWithInterface),
        SimpleFakeEntry('enforceChosenWorker', ClassWithInterface),
        SimpleFakeEntry('WorkerChoiceParameter', ClassWithInterface),
    ],
}


def provide_worker_fake_entries(group):
    """
    give a set of fake entries for known groups
    """
    return _WORKER_FAKE_ENTRIES.get(group, [])


class TestWorkerPluginsTransition(unittest.TestCase):

    def setUp(self):
        buildbot.plugins.db._DB = buildbot.plugins.db._PluginDB()

        with mock.patch('buildbot.plugins.db.iter_entry_points',
                        provide_worker_fake_entries):
            self.worker_ns = db.get_plugins('worker')
            self.buildslave_ns = db.get_plugins('buildslave')
            self.util_ns = db.get_plugins('util')

    def test_new_api(self):
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertTrue(self.worker_ns.Worker is ClassWithInterface)

    def test_old_api_access_produces_warning(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=r"'buildbot\.plugins\.buildslave' plugins "
                                "namespace is deprecated"):
            # Old API, with warning
            self.assertTrue(
                self.buildslave_ns.BuildSlave is ClassWithInterface)

    def test_new_api_through_old_namespace(self):
        # Access of newly named workers through old entry point is an error.
        with assertProducesWarning(DeprecatedWorkerNameWarning,
                                   message_pattern="namespace is deprecated"):
            self.assertRaises(
                AttributeError, lambda: self.buildslave_ns.Worker)

    def test_old_api_through_new_namespace(self):
        # Access of old-named workers through new API is an error.
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertRaises(AttributeError,
                              lambda: self.worker_ns.BuildSlave)

    def test_old_api_thirdparty(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=r"'buildbot\.plugins\.buildslave' plugins "
                                "namespace is deprecated"):
            # Third party plugins that use old API should work through old API.
            self.assertTrue(
                self.buildslave_ns.thirdparty is ClassWithInterface)

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            # Third party plugins that use old API should work through new API.
            self.assertTrue(
                self.worker_ns.thirdparty is ClassWithInterface)

    def test_old_api_thirdparty_deep(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=r"'buildbot\.plugins\.buildslave' plugins "
                                "namespace is deprecated"):
            self.assertTrue(
                self.buildslave_ns.deep.thirdparty is ClassWithInterface)

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertTrue(
                self.worker_ns.deep.thirdparty is ClassWithInterface)

    def test_new_api_thirdparty(self):
        # Third party plugins that use new API should work only through
        # new API.
        with assertProducesWarning(DeprecatedWorkerNameWarning,
                                   message_pattern="namespace is deprecated"):
            self.assertRaises(AttributeError,
                              lambda: self.buildslave_ns.newthirdparty)
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertTrue(
                self.worker_ns.newthirdparty is ClassWithInterface)

    def test_new_api_thirdparty_deep(self):
        # TODO: Why it's not AttributeError (as in tests above), but
        # PluginDBError?
        with assertProducesWarning(DeprecatedWorkerNameWarning,
                                   message_pattern="namespace is deprecated"):
            self.assertRaises(PluginDBError,
                              lambda: self.buildslave_ns.deep.newthirdparty)
        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertTrue(
                self.worker_ns.deep.newthirdparty is ClassWithInterface)

    def test_util_SlaveLock_import(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=re.escape(
                    "'buildbot.util.SlaveLock' is deprecated, "
                    "use 'buildbot.util.WorkerLock' instead")):
            deprecated = self.util_ns.SlaveLock

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertIdentical(deprecated, ClassWithInterface)

    def test_util_enforceChosenSlave_import(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=re.escape(
                    "'buildbot.util.enforceChosenSlave' is deprecated, "
                    "use 'buildbot.util.enforceChosenWorker' instead")):
            deprecated = self.util_ns.enforceChosenSlave

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertIdentical(deprecated, ClassWithInterface)

    def test_util_BuildslaveChoiceParameter_import(self):
        with assertProducesWarning(
                DeprecatedWorkerNameWarning,
                message_pattern=re.escape(
                    "'buildbot.util.BuildslaveChoiceParameter' is deprecated, "
                    "use 'buildbot.util.WorkerChoiceParameter' instead")):
            deprecated = self.util_ns.BuildslaveChoiceParameter

        with assertNotProducesWarnings(DeprecatedWorkerAPIWarning):
            self.assertIdentical(deprecated, ClassWithInterface)
