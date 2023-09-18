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

import warnings
from unittest import mock

from twisted.trial import unittest
from zope.interface import implementer

import buildbot.plugins.db
from buildbot.errors import PluginDBError
from buildbot.interfaces import IPlugin
from buildbot.test.util.warnings import assertProducesWarning

# buildbot.plugins.db needs to be imported for patching, however just 'db' is
# much shorter for using in tests
db = buildbot.plugins.db


class FakeEntry:

    """
    An entry suitable for unit tests
    """

    def __init__(self, name, group, fail_require, value, warnings=None):
        self._name = name
        self._group = group
        self._fail_require = fail_require
        self._value = value
        self._warnings = [] if warnings is None else warnings

    @property
    def name(self):
        return self._name

    @property
    def group(self):
        return self._group

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
        for w in self._warnings:
            warnings.warn(w, DeprecationWarning)
        return self._value


class FakeDistribution():
    def __init__(self, name, version, fake_entries_distribution):
        self.entry_points = fake_entries_distribution
        self.version = version
        self.metadata = {}
        self.metadata['Name'] = name
        self.metadata['Version'] = version


class FakeDistributionNoMetadata():
    def __init__(self, name, version, fake_entries_distribution):
        self.entry_points = fake_entries_distribution
        self.metadata = {}


class ITestInterface(IPlugin):

    """
    test interface
    """
    def hello(self):
        pass


@implementer(ITestInterface)
class ClassWithInterface:

    """
    a class to implement a simple interface
    """

    def __init__(self, name=None):
        self._name = name

    def hello(self, name=None):
        'implement the required method'
        return name or self._name


class ClassWithNoInterface:

    """
    just a class
    """


# NOTE: buildbot.plugins.db prepends the group with common namespace --
# 'buildbot.'
_FAKE_ENTRIES = {
    'buildbot.interface': [
        FakeEntry('good', 'buildbot.interface', False, ClassWithInterface),
        FakeEntry('deep.path', 'buildbot.interface', False, ClassWithInterface)
    ],
    'buildbot.interface_warnings': [
        FakeEntry('good', 'buildbot.interface_warnings', False, ClassWithInterface,
                  warnings=['test warning']),
        FakeEntry('deep.path', 'buildbot.interface_warnings', False, ClassWithInterface,
                  warnings=['test warning'])
    ],
    'buildbot.interface_failed': [
        FakeEntry('good', 'buildbot.interface_failed', True, ClassWithInterface)
    ],
    'buildbot.no_interface': [
        FakeEntry('good', 'buildbot.no_interface', False, ClassWithNoInterface)
    ],
    'buildbot.no_interface_again': [
        FakeEntry('good', 'buildbot.no_interface_again', False, ClassWithNoInterface)
    ],
    'buildbot.no_interface_failed': [
        FakeEntry('good', 'buildbot.no_interface_failed', True, ClassWithNoInterface)
    ],
    'buildbot.duplicates': [
        FakeEntry('good', 'buildbot.duplicates', False, ClassWithNoInterface),
        FakeEntry('good', 'buildbot.duplicates', False, ClassWithNoInterface)
    ]
}


def fake_find_distribution_info(entry_name, entry_group):
    return ('non-existent', 'irrelevant')


class TestFindDistributionInfo(unittest.TestCase):
    def test_exists_in_1st_ep(self):
        distributions = [
            FakeDistribution('name_1', 'version_1',
                [
                    FakeEntry('ep1', 'group_ep1', False, ClassWithInterface),
                ]
            )
        ]
        with mock.patch('buildbot.plugins.db.distributions', return_value=distributions):
            result = buildbot.plugins.db.find_distribution_info('ep1', 'group_ep1')
            self.assertEqual(('name_1', 'version_1'), result)

    def test_exists_in_last_ep(self):
        distributions = [
            FakeDistribution('name_1', 'version_1',
                [
                    FakeEntry('ep1', 'group_ep1', False, ClassWithInterface),
                    FakeEntry('ep2', 'group_ep2', False, ClassWithNoInterface)
                ]
            )
        ]
        with mock.patch('buildbot.plugins.db.distributions', return_value=distributions):
            result = buildbot.plugins.db.find_distribution_info('ep2', 'group_ep2')
            self.assertEqual(('name_1', 'version_1'), result)

    def test_no_group(self):
        distributions = [
            FakeDistribution('name_1', 'version_1',
                [
                    FakeEntry('ep1', 'group_ep1', False, ClassWithInterface),
                ]
            )
        ]
        with mock.patch('buildbot.plugins.db.distributions', return_value=distributions):
            with self.assertRaises(PluginDBError):
                buildbot.plugins.db.find_distribution_info('ep1', 'no_group')

    def test_no_name(self):
        distributions = [
            FakeDistribution('name_1', 'version_1',
                [
                    FakeEntry('ep1', 'group_ep1', False, ClassWithInterface),
                ]
            )
        ]
        with mock.patch('buildbot.plugins.db.distributions', return_value=distributions):
            with self.assertRaises(PluginDBError):
                buildbot.plugins.db.find_distribution_info('no_name', 'group_ep1')

    def test_no_name_no_group(self):
        distributions = [
            FakeDistribution('name_1', 'version_1',
                [
                    FakeEntry('ep1', 'group_ep1', False, ClassWithInterface),
                ]
            )
        ]
        with mock.patch('buildbot.plugins.db.distributions', return_value=distributions):
            with self.assertRaises(PluginDBError):
                buildbot.plugins.db.find_distribution_info('no_name', 'no_group')

    def test_no_metadata_error_in_1st_dist(self):
        distributions = [
            FakeDistributionNoMetadata('name_1', 'version_1',
                [
                    FakeEntry('ep1', 'group_ep1', False, ClassWithInterface),
                ]
            )
        ]
        with mock.patch('buildbot.plugins.db.distributions', return_value=distributions):
            with self.assertRaises(PluginDBError):
                buildbot.plugins.db.find_distribution_info('ep1', 'group_ep1')

    def test_no_metadata_error_in_last_dist(self):
        distributions = [
            FakeDistribution('name_1', 'version_1',
                [
                    FakeEntry('ep1', 'group_ep1', False, ClassWithInterface),
                ]
            ),
            FakeDistributionNoMetadata('name_2', 'version_2',
                [
                    FakeEntry('ep2', 'group_ep2', False, ClassWithInterface),
                ]
            )
        ]
        with mock.patch('buildbot.plugins.db.distributions', return_value=distributions):
            with self.assertRaises(PluginDBError):
                buildbot.plugins.db.find_distribution_info('ep2', 'group_ep2')

    def test_exists_in_last_dist_1st_ep(self):
        distributions = [
            FakeDistribution('name_1', 'version_1',
                [
                    FakeEntry('ep1', 'group_ep1', False, ClassWithInterface),
                ]),
            FakeDistribution('name_2', 'version_2',
                [
                    FakeEntry('ep2', 'group_ep2', False, ClassWithInterface),
                    FakeEntry('ep3', 'group_ep3', False, ClassWithNoInterface)
                ])
        ]
        with mock.patch('buildbot.plugins.db.distributions', return_value=distributions):
            result = buildbot.plugins.db.find_distribution_info('ep2', 'group_ep2')
            self.assertEqual(('name_2', 'version_2'), result)

    def test_exists_in_last_dist_last_ep(self):
        distributions = [
            FakeDistribution('name_1', 'version_1',
                [
                    FakeEntry('ep1', 'group_ep1', False, ClassWithInterface),
                ]),
            FakeDistribution('name_2', 'version_2',
                [
                    FakeEntry('ep2', 'group_ep2', False, ClassWithInterface),
                    FakeEntry('ep3', 'group_ep3', False, ClassWithNoInterface)
                ])
        ]
        with mock.patch('buildbot.plugins.db.distributions', return_value=distributions):
            result = buildbot.plugins.db.find_distribution_info('ep3', 'group_ep3')
            self.assertEqual(('name_2', 'version_2'), result)

    def test_1st_dist_no_ep(self):
        distributions = [
            FakeDistribution('name_1', 'version_1', []),
            FakeDistribution('name_2', 'version_2',
                [
                    FakeEntry('ep2', 'group_ep2', False, ClassWithInterface),
                ])
        ]
        with mock.patch('buildbot.plugins.db.distributions', return_value=distributions):
            result = buildbot.plugins.db.find_distribution_info('ep2', 'group_ep2')
            self.assertEqual(('name_2', 'version_2'), result)

    def test_exists_in_2nd_dist_ep_no_metadada(self):
        distributions = [
            FakeDistribution('name_1', 'version_1',
                [
                    FakeEntry('ep1', 'group_ep1', False, ClassWithInterface),
                ]),
            FakeDistributionNoMetadata('name_2', 'version_2',
                [
                    FakeEntry('ep2', 'group_ep2', False, ClassWithInterface),
                ]
            )
        ]
        with mock.patch('buildbot.plugins.db.distributions', return_value=distributions):
            with self.assertRaises(PluginDBError):
                buildbot.plugins.db.find_distribution_info('ep2', 'group_ep2')

    def test_same_groups_different_ep(self):
        distributions = [
            FakeDistribution('name_1', 'version_1',
                [
                    FakeEntry('ep1', 'group_ep1', False, ClassWithInterface),
                ]
            ),
            FakeDistribution('name_2', 'version_2',
                [
                    FakeEntry('ep2', 'group_ep1', False, ClassWithInterface),
                ])
        ]
        with mock.patch('buildbot.plugins.db.distributions', return_value=distributions):
            result = buildbot.plugins.db.find_distribution_info('ep2', 'group_ep1')
            self.assertEqual(('name_2', 'version_2'), result)

    def test_same_ep_different_groups(self):
        distributions = [
            FakeDistribution('name_1', 'version_1',
                [
                    FakeEntry('ep1', 'group_ep1', False, ClassWithInterface),
                ]
            ),
            FakeDistribution('name_2', 'version_2',
                [
                    FakeEntry('ep1', 'group_ep2', False, ClassWithInterface),
                ])
        ]
        with mock.patch('buildbot.plugins.db.distributions', return_value=distributions):
            result = buildbot.plugins.db.find_distribution_info('ep1', 'group_ep2')
            self.assertEqual(('name_2', 'version_2'), result)


def provide_fake_entry_points():
    return _FAKE_ENTRIES


_fake_find_distribution_info_dups_counter = 0


def fake_find_distribution_info_dups(entry_name, entry_group):
    # entry_name is always 'good'
    global _fake_find_distribution_info_dups_counter
    if _fake_find_distribution_info_dups_counter == 0:
        _fake_find_distribution_info_dups_counter += 1
        return ('non-existent', 'module_first')
    else:  # _fake_find_distribution_info_dups_counter == 1:
        _fake_find_distribution_info_dups_counter = 0
        return ('non-existent', 'module_second')


@mock.patch('buildbot.plugins.db.entry_points', provide_fake_entry_points)
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

    @mock.patch('buildbot.plugins.db.find_distribution_info', fake_find_distribution_info)
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

        with self.assertRaises(AttributeError):
            getattr(plugins, 'bad')
        with self.assertRaises(PluginDBError):
            plugins.get('bad')
        with self.assertRaises(PluginDBError):
            plugins.get('good.extra')

    @mock.patch('buildbot.plugins.db.find_distribution_info', fake_find_distribution_info)
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

    @mock.patch('buildbot.plugins.db.find_distribution_info', fake_find_distribution_info)
    def test_interface_warnings(self):
        # we should not get no warnings when not trying to access the plugin
        plugins = db.get_plugins('interface_warnings', interface=ITestInterface)
        self.assertTrue('good' in plugins.names)
        self.assertTrue('deep.path' in plugins.names)

        # we should get warning when trying to access the plugin
        with assertProducesWarning(DeprecationWarning, "test warning"):
            _ = plugins.get('good')
        with assertProducesWarning(DeprecationWarning, "test warning"):
            _ = plugins.good
        with assertProducesWarning(DeprecationWarning, "test warning"):
            _ = plugins.get('deep.path')
        with assertProducesWarning(DeprecationWarning, "test warning"):
            _ = plugins.deep.path

    def test_required_interface_not_provided(self):
        plugins = db.get_plugins('no_interface_again',
                                 interface=ITestInterface)
        self.assertTrue(plugins._interface is ITestInterface)
        with self.assertRaises(PluginDBError):
            plugins.get('good')

    def test_no_interface_provided(self):
        plugins = db.get_plugins('no_interface')
        self.assertFalse(plugins.get('good') is None)

    @mock.patch('buildbot.plugins.db.find_distribution_info', fake_find_distribution_info_dups)
    def test_failure_on_dups(self):
        with self.assertRaises(PluginDBError):
            db.get_plugins('duplicates', load_now=True)

    @mock.patch('buildbot.plugins.db.find_distribution_info', fake_find_distribution_info)
    def test_get_info_on_a_known_plugin(self):
        plugins = db.get_plugins('interface')
        self.assertEqual(('non-existent', 'irrelevant'), plugins.info('good'))

    def test_failure_on_unknown_plugin_info(self):
        plugins = db.get_plugins('interface')
        with self.assertRaises(PluginDBError):
            plugins.info('bad')

    def test_failure_on_unknown_plugin_get(self):
        plugins = db.get_plugins('interface')
        with self.assertRaises(PluginDBError):
            plugins.get('bad')


class SimpleFakeEntry(FakeEntry):

    def __init__(self, name, value):
        super().__init__(name, 'group', False, value)


_WORKER_FAKE_ENTRIES = {
    'buildbot.worker': [
        SimpleFakeEntry('Worker', ClassWithInterface),
        SimpleFakeEntry('EC2LatentWorker', ClassWithInterface),
        SimpleFakeEntry('LibVirtWorker', ClassWithInterface),
        SimpleFakeEntry('OpenStackLatentWorker', ClassWithInterface),
        SimpleFakeEntry('newthirdparty', ClassWithInterface),
        SimpleFakeEntry('deep.newthirdparty', ClassWithInterface),
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
