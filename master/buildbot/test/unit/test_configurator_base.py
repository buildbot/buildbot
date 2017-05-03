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

from twisted.trial import unittest

from buildbot.configurators import ConfiguratorBase
from buildbot.test.util import configurators


class ConfiguratorBaseTests(configurators.ConfiguratorMixin, unittest.SynchronousTestCase):
    ConfiguratorClass = ConfiguratorBase

    def test_basic(self):
        self.setupConfigurator()
        self.assertEqual(self.config_dict, {
            'schedulers': [],
            'protocols': {},
            'workers': [],
            'builders': []
        })
        self.assertEqual(self.configurator.workers, [])

    def test_worker_vs_slaves(self):
        """The base configurator uses the slaves config if it exists already"""
        self.config_dict['slaves'] = [1]  # marker
        self.setupConfigurator()
        self.assertEqual(self.config_dict, {
            'schedulers': [],
            'slaves': [1],
            'builders': [],
            'protocols': {}
        })
        self.assertEqual(self.configurator.workers, [1])
