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

from buildbot.config import MasterConfig


class ConfiguratorMixin(object):

    """
    Support for testing configurators.

    @ivar configurator: the configurator under test
    @ivar config_dict: the config dict that the configurator is modifying
    """
    def setUp(self):
        self.config_dict = {}

    def setupConfigurator(self, *args, **kwargs):
        self.configurator = self.ConfiguratorClass(*args, **kwargs)
        return self.configurator.configure(self.config_dict)

    def expectWorker(self, name, klass):
        if 'workers' in self.config_dict and 'slaves' in self.config_dict:
            self.fail("both 'workers' and 'slaves' are in the config dict!")
        for worker in self.config_dict.get('workers', []) + self.config_dict.get('slaves', []):
            if isinstance(worker, klass) and worker.name == name:
                return worker
        self.fail("expected a worker named {} of class {}".format(name, klass))

    def expectScheduler(self, name, klass):
        for scheduler in self.config_dict['schedulers']:
            if scheduler.name == name and isinstance(scheduler, klass):
                return scheduler
        self.fail("expected a scheduler named {} of class {}".format(name, klass))

    def expectBuilder(self, name):
        for builder in self.config_dict['builders']:
            if builder.name == name:
                return builder
        self.fail("expected a builder named {}".format(name))

    def expectBuilderHasSteps(self, name, step_classes):
        builder = self.expectBuilder(name)
        for step_class in step_classes:
            found = [
                step
                for step in builder.factory.steps if step.factory == step_class
            ]
            if not found:
                self.fail("expected a buildstep of {!r} in {}".format(step_class, name))

    def expectNoConfigError(self):
        config = MasterConfig()
        config.loadFromDict(self.config_dict, "test")
