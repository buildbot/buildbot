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

from buildbot.configurators import ConfiguratorBase
from buildbot.test.util import configurators


class ConfiguratorBaseTests(configurators.ConfiguratorMixin, unittest.SynchronousTestCase):
    ConfiguratorClass = ConfiguratorBase

    def test_basic(self):
        self.setupConfigurator()
        self.assertEqual(
            self.config_dict,
            {
                'schedulers': [],
                'protocols': {},
                'builders': [],
                'workers': [],
                'projects': [],
                'secretsProviders': [],
                'www': {},
            },
        )
        self.assertEqual(self.configurator.workers, [])
