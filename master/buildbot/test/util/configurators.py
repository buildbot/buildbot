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

from __future__ import annotations

from typing import TYPE_CHECKING
from typing import Any

from buildbot.config.master import MasterConfig

if TYPE_CHECKING:
    from twisted.trial import unittest

    _ConfiguratorMixinBase = unittest.TestCase
else:
    _ConfiguratorMixinBase = object


class ConfiguratorMixin(_ConfiguratorMixinBase):
    """
    Support for testing configurators.

    @ivar configurator: the configurator under test
    @ivar config_dict: the config dict that the configurator is modifying
    """

    def setUp(self) -> None:
        self.config_dict: dict[str, Any] = {}

    def setupConfigurator(self, *args: Any, **kwargs: Any) -> Any:
        self.configurator = self.ConfiguratorClass(*args, **kwargs)  # type: ignore[attr-defined]
        return self.configurator.configure(self.config_dict)

    def expectWorker(self, name: str, klass: type) -> Any:
        if 'workers' in self.config_dict and 'slaves' in self.config_dict:
            self.fail("both 'workers' and 'slaves' are in the config dict!")
        for worker in self.config_dict.get('workers', []) + self.config_dict.get('slaves', []):
            if isinstance(worker, klass) and worker.name == name:  # type: ignore[attr-defined]
                return worker
        self.fail(f"expected a worker named {name} of class {klass}")
        return None

    def expectScheduler(self, name: str, klass: type) -> Any:
        for scheduler in self.config_dict['schedulers']:
            if scheduler.name == name and isinstance(scheduler, klass):
                return scheduler
        self.fail(f"expected a scheduler named {name} of class {klass}")
        return None

    def expectBuilder(self, name: str) -> Any:
        for builder in self.config_dict['builders']:
            if builder.name == name:
                return builder
        self.fail(f"expected a builder named {name}")
        return None

    def expectBuilderHasSteps(self, name: str, step_classes: list[type]) -> None:
        builder = self.expectBuilder(name)
        for step_class in step_classes:
            found = [step for step in builder.factory.steps if step.step_class == step_class]
            if not found:
                self.fail(f"expected a buildstep of {step_class!r} in {name}")

    def expectNoConfigError(self) -> None:
        master_config = MasterConfig()
        master_config.loadFromDict(self.config_dict, "test")
