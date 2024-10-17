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
#

"""This module holds configurators, which helps setup schedulers, builders, steps,
for a very specific purpose.
Higher level interfaces to buildbot configurations components.
"""

from zope.interface import implementer

from buildbot.interfaces import IConfigurator


@implementer(IConfigurator)
class ConfiguratorBase:
    """
    I provide base helper methods for configurators
    """

    def __init__(self):
        pass

    def configure(self, config_dict):
        self.config_dict = c = config_dict
        self.schedulers = c.setdefault('schedulers', [])
        self.protocols = c.setdefault('protocols', {})
        self.builders = c.setdefault('builders', [])
        self.workers = c.setdefault('workers', [])
        self.projects = c.setdefault('projects', [])
        self.secretsProviders = c.setdefault('secretsProviders', [])
        self.www = c.setdefault('www', {})
